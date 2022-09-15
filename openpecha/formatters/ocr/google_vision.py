import gzip
import json
import math
import re
from enum import Enum
from pathlib import Path
import statistics
import logging

import datetime
from datetime import timezone
import requests
from pathlib import Path

from openpecha.core.annotation import Page, Span
from openpecha.core.annotations import BaseAnnotation, Language, OCRConfidence
from openpecha.core.layer import Layer, LayerEnum, OCRConfidenceLayer
from openpecha.core.ids import get_base_id
from openpecha.core.metadata import InitialPechaMetadata, InitialCreationType, LicenseType, Copyright_copyrighted, Copyright_unknown, Copyright_public_domain
from openpecha.formatters import BaseFormatter
from openpecha.utils import dump_yaml, gzip_str

from openpecha.buda.api import get_buda_scan_info, get_image_list, image_group_to_folder_name

class GoogleVisionBDRCFileProvider(OCRFileProvider):
    def __init__(self, bdrc_scan_id, ocr_import_info, ocr_disk_path=None, mode="local"):
        # ocr_base_path should be the output/ folder in the case of BDRC OCR files
        self.ocr_import_info = ocr_import_info
        self.ocr_disk_path = ocr_disk_path
        self.bdrc_scan_id = bdrc_scan_id
        self.mode = mode

    def get_image_list(self, image_group_id):
        buda_il = get_image_list(self.bdrc_scan_id, image_group_id)
        # format should be a list of image_id (/ file names)
        return map(lambda ii: ii["filename"], buda_il)

    def get_source_info(self):
        return get_buda_scan_info(self.bdrc_scan_id)

    def get_image_data(self, image_group_id, image_id):
        # TODO: implement the following modes:
        #  - "s3" (just read images from s3)
        #  - "s3-localcache" (cache s3 files on disk)
        # TODO: handle case where only zip archives are present on s3, one per volume.
        #       This should be indicated in self.ocr_import_info["ocr_info"]
        vol_folder = image_group_to_folder_name(self.bdrc_scan_id, image_group_id)
        expected_ocr_filename = image_id[:image_id.rfind('.')]+".json.gz"
        image_ocr_path = ocr_disk_path / vol_folder / expected_ocr_filename
        ocr_object = None
        try:
            ocr_object = json.load(gzip.open(str(expected_ocr_path), "rb"))
        except:
            logging.exception("could not read "+str(expected_ocr_path))
        return ocr_object

class GoogleVisionFormatter(OCRFormatter):
    """
    OpenPecha Formatter for Google OCR JSON output of scanned pecha.
    """

    def __init__(self, output_path=None, metadata=None):
        super().__init__(output_path, metadata)

    def has_space_attached(self, symbol):
        """Checks if symbol has space followed by it or not

        Args:
            symbol (dict): symbol info

        Returns:
            boolean: True if the symbol has space followed by it
        """
        if ('property' in symbol and 
                'detectedBreak' in symbol['property'] and 
                'type' in symbol['property']['detectedBreak'] and 
                symbol['property']['detectedBreak']['type'] == "SPACE"):
            return True
        return False

    def get_language_code(self, poly):
        lang = ""
        properties = poly.get("property", {})
        if properties:
            languages = properties.get("detectedLanguages", [])
            if languages:
                lang = languages[0]['languageCode']
        if lang == "" || lang == "und":
            # this is not always true but replacing it with None is worse
            # with our current data
            return self.default_language
        if lang in ["bo", "en", "zh"]:
            return lang
        if lang == "dz":
            return "bo"
        # English is a kind of default for our purpose
        return "en"

    def dict_to_bbox(self, word):
        """Convert bounding poly to BBox object

        Args:
            word (dict): bounding poly of a word infos

        Returns:
            obj: BBox object of bounding poly
        """
        text = word.get('text', '')
        confidence = word.get('confidence')
        language = self.get_language_code(word)
        if 'boundingBox' not in word or 'vertices' not in word['boundingBox']:
            return None
        vertices = word['boundingBox']['vertices']
        if len(vertices != 4) or 'x' not in vertices[0] or 'x' not in vertices[1] or 'y' not in vertices[0] or 'y' not n vertices[2]:
            return None
        return BBox(vertices[0]['x'], vertices[1]['x'], vertices[0]['y'], vertices[2]['y'], text=text, confidence=confidence, language=language)

    def get_char_base_bboxes(self, response):
        """Return bounding polys in page response

        Args:
            response (dict): google ocr output of a page

        Returns:
            list: list of BBox object which saves required info of a bounding poly
        """
        bboxes = []
        cur_word = ""
        for page in response['fullTextAnnotation']['pages']:
            for block in page['blocks']:
                for paragraph in block['paragraphs']:
                    for word in paragraph['words']:
                        for symbol in word['symbols']:
                            cur_word += symbol['text']
                            if self.has_space_attached(symbol):
                                cur_word += " "
                        word['text'] = cur_word
                        cur_word = ""
                        bbox = self.dict_to_bbox(word)
                        bboxes.append(bbox)
        return bboxes

    def get_bboxes_for_page(self, image_group_id, image_filename):
        ocr_object = self.data_provider.get_image_data(image_group_id, image_filename)
        try:
            page_content = ocr_object["textAnnotations"][0]["description"]
        except Exception:
            logging.error("OCR page is empty (no textAnnotations[0]/description)")
            return
        bboxes = self.get_char_base_bboxes(ocr_object)
        return bboxes