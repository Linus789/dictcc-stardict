#!/usr/bin/env python
from pyglossary.glossary import Glossary
import pyparsing as pp
from collections import namedtuple
from collections import defaultdict
import html
import unicodedata
from datetime import date
import os

def get_language_pair(input_file: str):
    with open(input_file) as f:
        return f.readline().removeprefix("#").strip().split()[0].lower()

class FieldParser:
    def __init__(self):
        self._init_line_parser()
        self._init_replace_abbreviations()
        self._test_get_source_words()

    def _init_line_parser(self):
        locMarker = pp.Empty().set_parse_action(lambda string, location, tokens: location)
        endlocMarker = locMarker.copy()
        endlocMarker.callPreparse = False

        Round = self.round = namedtuple("Round", ["value"])
        round = pp.Forward()
        round << locMarker("start") + pp.Suppress('(') + pp.ZeroOrMore(round | pp.CharsNotIn(")", exact=1)) + pp.Suppress(')') + endlocMarker("end")
        round.setParseAction(lambda string, location, tokens: Round(value=string[tokens.start+1:tokens.end-1]))

        Square = self.square = namedtuple("Square", ["value"])
        square = pp.Forward()
        square << locMarker("start") + pp.Suppress('[') + pp.ZeroOrMore(square | pp.CharsNotIn("]", exact=1)) + pp.Suppress(']') + endlocMarker("end")
        square.setParseAction(lambda string, location, tokens: Square(value=string[tokens.start+1:tokens.end-1]))

        Curly = self.curly = namedtuple("Curly", ["value"])
        curly = pp.Forward()
        curly << locMarker("start") + pp.Suppress('{') + pp.ZeroOrMore(curly | pp.CharsNotIn("}", exact=1)) + pp.Suppress('}') + endlocMarker("end")
        curly.setParseAction(lambda string, location, tokens: Curly(value=string[tokens.start+1:tokens.end-1]))

        Angle = self.angle = namedtuple("Angle", ["value"])
        angle = pp.Forward()
        angle << locMarker("start") + pp.Suppress('<') + pp.ZeroOrMore(angle | pp.CharsNotIn(">", exact=1)) + pp.Suppress('>') + endlocMarker("end")
        angle.setParseAction(lambda string, location, tokens: Angle(value=string[tokens.start+1:tokens.end-1]))

        Word = self.word = namedtuple("Word", ["value"])
        word = locMarker("start") +  pp.CharsNotIn(" ([{<") + endlocMarker("end")
        word.setParseAction(lambda string, location, tokens: Word(value=string[tokens.start:tokens.end]))

        brackets = round | square | curly | angle
        self.expr = pp.ZeroOrMore(word | brackets | pp.Suppress(pp.Word(" ")))

    def _init_replace_abbreviations(self):
        # https://www.dict.cc/guidelines/
        self.abbreviations_synonyms = {
            "en": {
                "sth.": {"something"},
                "sb.": {"somebody"},
                "sb.'s": {"somebody's"},
                "sb./sth.": {"somebody", "something", "somebody/something"},
            },
            "de": {
                "jd.": {"jemand"},
                "jds.": {"jemandes"},
                "jdm.": {"jemandem"},
                "jdn.": {"jemanden"},
                "etw.": {"etwas"},
                "jd./etw.": {"jemand", "etwas", "jemand/etwas"},
                "jds./etw.": {"jemandes", "etwas", "jemandes/etwas"},
                "jdm./etw.": {"jemandem", "etwas", "jemandem/etwas"},
                "jdn./etw.": {"jemanden", "etwas", "jemanden/etwas"},
            },
        }

        self.find_abbreviations_exprs = {}

        Abbreviation = self.abbreviation = namedtuple("Abbreviation", ["value"])
        locMarker = pp.Empty().set_parse_action(lambda string, location, tokens: location)
        endlocMarker = locMarker.copy()
        endlocMarker.callPreparse = False

        for lang, abbreviation_replacements in self.abbreviations_synonyms.items():
            abbreviations = list(abbreviation_replacements.keys())

            if not abbreviations:
                continue

            find_abbreviations_expr = pp.WordStart() + locMarker("start") + pp.Literal(abbreviations[0]) + pp.WordEnd() + endlocMarker("end")

            for other_abbreviation in abbreviations[1:]:
                find_abbreviations_expr = find_abbreviations_expr | (pp.WordStart() + locMarker("start") + pp.Literal(other_abbreviation) + pp.WordEnd() + endlocMarker("end"))

            find_abbreviations_expr.setParseAction(lambda string, location, tokens: Abbreviation(value=string[tokens.start:tokens.end]))
            find_abbreviations_expr = pp.ZeroOrMore(find_abbreviations_expr | pp.CharsNotIn("", exact=1))
            find_abbreviations_expr.leave_whitespace()

            self.find_abbreviations_exprs[lang] = find_abbreviations_expr

    def parse_tokens(self, s: str):
        return self.expr.parse_string(s)

    def get_possible_source_words(self, field: str, word_class: str, lang: str, make_abbreviations_optional: bool = True, replace_abbreviations: bool = True):
        # Prepare abbreviations
        if make_abbreviations_optional:
            # https://www.dict.cc/guidelines/
            optional_abbreviations = {
                "en": {
                    "any": {"start_or_end": {"sth.", "sb.", "sb.'s", "sb./sth."}},
                    "verb": {"start": {"to"}},
                },
                "de": {
                    "any": {"start_or_end": {"jd.", "jds.", "jdm.", "jdn.", "etw.", "jd./etw.", "jds./etw.", "jdm./etw.", "jdn./etw."}}
                },
            }

            lang_abbreviations = optional_abbreviations.get(lang, {})
            possible_abbreviations = lang_abbreviations.get("any", {})

            for where, values in lang_abbreviations.get(word_class, {}).items():
                if where in possible_abbreviations:
                    possible_abbreviations[where].update(values)
                else:
                    possible_abbreviations[where] = values

            if "start_or_end" in possible_abbreviations:
                start_or_end_abbreviations = possible_abbreviations.pop("start_or_end")

                if "start" in possible_abbreviations:
                    possible_abbreviations["start"].update(start_or_end_abbreviations)
                else:
                    possible_abbreviations["start"] = start_or_end_abbreviations

                if "end" in possible_abbreviations:
                    possible_abbreviations["end"].update(start_or_end_abbreviations)
                else:
                    possible_abbreviations["end"] = start_or_end_abbreviations
        else:
            possible_abbreviations = {}

        # Iterate over tokens
        tokens = self.parse_tokens(field)
        source_words = None
        finished_words = set()
        already_encountered_word = False
        try:
            last_word_index = [i for i, token in enumerate(tokens) if type(token) == self.word][-1]
        except IndexError:
            last_word_index = None

        for index, token in enumerate(tokens):
            if make_abbreviations_optional and possible_abbreviations and type(token) == self.word:
                if index == last_word_index and token.value in possible_abbreviations.get("end", set()):
                    if source_words is None:
                        source_words = {token.value}
                    else:
                        finished_words |= set(source_words)
                        source_words = {f"{word} {token.value}" for word in source_words}

                    already_encountered_word = True
                    continue

                if not already_encountered_word and token.value in possible_abbreviations.get("start", set()):
                    if source_words is None:
                        source_words = {token.value, ""}
                    else:
                        source_words = {f"{word} {token.value}" for word in source_words} | {token.value, ""}

                    already_encountered_word = True
                    continue

            if type(token) == self.word:
                if source_words is None:
                    source_words = {token.value}
                else:
                    source_words = {f"{word} {token.value}" for word in source_words}

                already_encountered_word = True
            elif type(token) == self.round:
                if source_words is None:
                    source_words = {token.value, ""}
                else:
                    source_words |= {f"{word} {token.value}" for word in source_words}

        if source_words is None:
            source_words = set()

        return_words = set()
        source_words = {stripped for word in (source_words | finished_words) if (stripped := " ".join(word.split()))}

        if replace_abbreviations and lang in self.find_abbreviations_exprs:
            replacements_for_lang = self.abbreviations_synonyms[lang]
            find_abbreviations_expr = self.find_abbreviations_exprs[lang]

            for word in source_words:
                split_word = find_abbreviations_expr.parse_string(word)
                build_words = None

                for sub_word in split_word:
                    if type(sub_word) != self.abbreviation:
                        if build_words is None:
                            build_words = {sub_word}
                        else:
                            build_words = {f"{build_word}{sub_word}" for build_word in build_words}
                    else:
                        current_replacements = replacements_for_lang[sub_word.value] | {sub_word.value}

                        if build_words is None:
                            build_words = current_replacements
                        else:
                            build_words = {f"{build_word}{extra_word}" for build_word in build_words for extra_word in current_replacements}

                if build_words is not None:
                    return_words.update(build_words)
        else:
            return_words = source_words

        return {stripped for word in return_words if (stripped := " ".join(word.split()))}

    def _test_get_source_words(self):
        print("-> Running tests...")
        assert self.get_possible_source_words("(wait) for me", None, "en") == {"for me", "wait for me"}
        assert self.get_possible_source_words("for me (myself)", None, "en") == {"for me", "for me myself"}
        assert self.get_possible_source_words("(wait) for me (myself)", None, "en") == {"for me", "for me myself", "wait for me", "wait for me myself"}
        assert self.get_possible_source_words("to the detriment of", None, "en") == {"to the detriment of"}
        assert self.get_possible_source_words("to squirm", "verb", "en") == {"to squirm", "squirm"}
        assert self.get_possible_source_words("to help sb.", "verb", "en") == {"to help", "help", "to help sb.", "help sb.", "to help somebody", "help somebody"}
        assert self.get_possible_source_words("sth. is off", "verb", "en") == {"sth. is off", "something is off", "is off"}
        assert self.get_possible_source_words("(go) to see the match", "verb", "en") == {"go to see the match", "to see the match", "see the match"}
        assert self.get_possible_source_words("(I think) sb. is running", "verb", "en") == {"I think sb. is running", "sb. is running", "I think somebody is running", "somebody is running", "is running"}
        assert self.get_possible_source_words("(I think) sb. is running", "verb", "en") == {"I think sb. is running", "sb. is running", "I think somebody is running", "somebody is running", "is running"}
        assert self.get_possible_source_words("(I think) sb. is running after sb.", "verb", "en") == {"I think sb. is running after sb.", "sb. is running after sb.", "is running after sb.", "I think sb. is running after", "sb. is running after", "I think somebody is running after sb.", "somebody is running after sb.", "I think sb. is running after somebody", "sb. is running after somebody", "I think somebody is running after somebody", "somebody is running after somebody", "is running after somebody", "I think somebody is running after", "somebody is running after", "is running after"}
        assert self.get_possible_source_words("(I think) sb. is running after sb. (right?)", "verb", "en") == {"I think sb. is running after sb.", "sb. is running after sb.", "is running after sb.", "I think sb. is running after", "sb. is running after", "is running after", "I think sb. is running after sb. right?", "sb. is running after sb. right?", "is running after sb. right?", "I think somebody is running after sb.", "I think sb. is running after somebody", "I think somebody is running after somebody", "somebody is running after sb.", "sb. is running after somebody", "somebody is running after somebody", "is running after somebody", "I think somebody is running after", "somebody is running after", "is running after", "I think somebody is running after sb. right?", "I think sb. is running after somebody right?", "I think somebody is running after somebody right?", "somebody is running after sb. right?", "sb. is running after somebody right?", "somebody is running after somebody right?", "is running after somebody right?"}
        assert self.get_possible_source_words("sb.", None, "en") == {"sb.", "somebody"}
        assert self.get_possible_source_words("(go to) sb.", None, "en") == {"go to sb.", "go to somebody", "go to", "sb.", "somebody"}
        assert self.get_possible_source_words("(go) to sb.", "verb", "en") == {"go to sb.", "go to somebody", "go to", "to sb.", "to somebody", "to", "sb.", "somebody"}
        assert self.get_possible_source_words("(go) to sb.", None, "en") == {"go to sb.", "go to somebody", "go to", "to somebody", "to sb.", "to"}
        assert self.get_possible_source_words("to go to", None, "en") == {"to go to"}
        assert self.get_possible_source_words("to go to", "verb", "en") == {"to go to", "go to"}
        assert self.get_possible_source_words("see sb./sth.", None, "en") == {"see sb./sth.", "see something", "see somebody", "see somebody/something", "see"}

def main(input_file: str, from_lang: str):
    lang_pair = get_language_pair(input_file)
    lang_pair_from, lang_pair_to = lang_pair.split("-")
    from_lang = from_lang.strip().lower()
    inverse_langs = None

    if from_lang == lang_pair_from:
        inverse_langs = False
    elif from_lang == lang_pair_to:
        inverse_langs = True

    if inverse_langs is None:
        raise Exception(f"{from_lang} is not allowed as source language. Available are {lang_pair_from} and {lang_pair_to}.")

    to_lang = lang_pair_to if not inverse_langs else lang_pair_from

    base_name = f"dictcc_{from_lang}-{to_lang}"
    try:
        os.mkdir(base_name)
    except FileExistsError:
        pass

    field_parser = FieldParser()
    dictionary = defaultdict(lambda: [])

    with open(input_file) as input_file:
        num_lines = len(input_file.readlines())
        input_file.seek(0)

        for index, line in enumerate(input_file.readlines(), start=1):
            print(f"\r-> Parsing line {index}/{num_lines}", end="")
            line = line.strip()

            if not line:
                continue

            if line[0] == "#":
                continue

            fields = line.split("\t")

            if len(fields) < 2:
                continue

            src, target = [unicodedata.normalize("NFC", html.unescape(field)) for field in fields[:2]]
            word_class = fields[2].strip().lower() if 2 < len(fields) else None

            if inverse_langs:
                src, target = target, src

            target = " ".join(target.split())

            if not target:
                continue

            for possible_source_word in field_parser.get_possible_source_words(src, word_class, from_lang):
                dictionary[possible_source_word].append(target)
        print()

    dictionary_num_entries = len(dictionary)
    translations_to_source_words = defaultdict(lambda: set())

    for index, (src, translations) in enumerate(dictionary.items(), start=1):
        print(f"\r-> Eliminating duplicates {index}/{dictionary_num_entries}", end="")
        translations_to_source_words[tuple(translations)].add(src)
    print()

    Glossary.init()
    glossary = Glossary()

    translations_num_entries = len(translations_to_source_words)
    for index, (translations, src_words) in enumerate(translations_to_source_words.items(), start=1):
        print(f"\r-> Creating entry {index}/{translations_num_entries}", end="")
        longest_src_word = sorted(src_words, key=lambda x: -len(x))[0]
        src_words.remove(longest_src_word)
        definition = "<ol>" + ''.join([f"<li>{translation}</li>" for translation in translations]) + "</ol>"

        entry = glossary.newEntry(
            longest_src_word,
            definition,
            defiFormat="h",  # "m" for plain text, "h" for HTML
        )

        for other_src_word in src_words:
            entry.addAlt(other_src_word)

        glossary.addEntryObj(entry)
    print()

    print(f"-> Sorting words...")
    glossary.sortWords(sortKeyName="stardict")

    print(f"-> Writing files...")
    os.chdir(base_name)
    glossary.setInfo("title", f"dict.cc {from_lang.upper()}-{to_lang.upper()}")
    glossary.setInfo("date", str(date.today()))
    glossary.write(f"{base_name}.ifo", format="Stardict")

if __name__ == "__main__":
    import argparse
    formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=40)
    parser = argparse.ArgumentParser(description='Convert dict.cc file to StarDict format', formatter_class=formatter)
    parser.add_argument('-f', '--file', dest='file', required=True, help='dict.cc file')
    parser.add_argument('-s', '--source-lang', metavar='LANG', dest='source_lang', required=True, help='source language')
    args = parser.parse_args()
    main(args.file, args.source_lang)
