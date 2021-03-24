from collections import defaultdict
from typing import Dict

from bs4 import BeautifulSoup

from openpecha.core.annotation import Ann, Span
from openpecha.core.layer import Layer, LayersEnum


class EditorParser:
    def __init__(self):
        self._reset()

    def _reset(self):
        self.layers: Dict[str, Dict[str, Layer]] = defaultdict(dict)
        self.base: Dict[str, str] = {}
        self.cur_base_char_idx = 0

    def _add_base(self, root, base_name):
        self.base[base_name] = root.text

    def _get_ann(self, tag):
        start = self.cur_base_char_idx
        end = start + len(tag.text)
        self.cur_base_char_idx = end
        span = Span(start=start, end=end)
        return Ann(span=span), tag["id"]

    @staticmethod
    def _get_empty_layer(layerEnum):
        return Layer(annotation_type=layerEnum, revision="0000", annotations={})

    def _get_layer(self, base_name, layerEnum):
        layer = self.layers[base_name].get(layerEnum, self._get_empty_layer(layerEnum))
        self.layers[base_name][layerEnum] = layer
        return layer

    def _add_ann(self, base_name, layerEnum, tag):
        ann, id_ = self._get_ann(tag)
        layer = self._get_layer(base_name, layerEnum)
        layer.annotations[id_] = ann

    def __handle_non_ann(self, text):
        self.cur_base_char_idx += len(text)

    def _parse_p_tag(self, base_name, p):
        for child in p.children:
            if isinstance(child, str):
                self.__handle_non_ann(child)
                continue

            tag_class = child["class"]
            if "book-title" in tag_class:
                self._add_ann(base_name, LayersEnum.book_title, child)
            elif "author" in tag_class:
                self._add_ann(base_name, LayersEnum.author, child)
            elif "chapter" in tag_class:
                self._add_ann(base_name, LayersEnum.chapter, child)
            elif "citation" in tag_class:
                self._add_ann(base_name, LayersEnum.citation, child)
            elif "root-text" in tag_class:
                self._add_ann(base_name, LayersEnum.tsawa, child)
            elif "sabche" in tag_class:
                self._add_ann(base_name, LayersEnum.sabche, child)

        # newline for p tag
        self.cur_base_char_idx += 1

    def parse(self, base_name, html):
        self._reset()

        root = BeautifulSoup(html, "html.parser")
        self._add_base(root, base_name)

        for p in root.find_all("p"):
            self._parse_p_tag(base_name, p)