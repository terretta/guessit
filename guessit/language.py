#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# GuessIt - A library for guessing information from filenames
# Copyright (c) 2011 Nicolas Wack <wackou@gmail.com>
#
# GuessIt is free software; you can redistribute it and/or modify it under
# the terms of the Lesser GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# GuessIt is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Lesser GNU General Public License for more details.
#
# You should have received a copy of the Lesser GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import unicode_literals
from guessit import fileutils
from guessit.country import Country
from guessit.textutils import to_unicode
import re
import logging

__all__ = [ 'is_iso_language', 'is_language', 'lang_set', 'Language',
            'ALL_LANGUAGES', 'ALL_LANGUAGES_NAMES', 'search_language' ]


log = logging.getLogger(__name__)


# downloaded from http://www.loc.gov/standards/iso639-2/ISO-639-2_utf-8.txt
#
# Description of the fields:
# "An alpha-3 (bibliographic) code, an alpha-3 (terminologic) code (when given),
# an alpha-2 code (when given), an English name, and a French name of a language
# are all separated by pipe (|) characters."
_iso639_contents = fileutils.load_file_in_same_dir(__file__,
                                                   'ISO-639-2_utf-8.txt').decode('utf-8')

# drop the BOM from the beginning of the file
_iso639_contents = _iso639_contents[1:]

language_matrix = [ l.strip().split('|')
                    for l in _iso639_contents.strip().split('\n') ]


# remove unused languages that shadow other common ones with a non-official form
for lang in language_matrix:
    if (lang[2] == 'se' or # Northern Sami shadows Swedish
        lang[2] == 'br'):  # Breton shadows Brazilian
        language_matrix.remove(lang)


lng3        = frozenset(l[0] for l in language_matrix if l[0])
lng3term    = frozenset(l[1] for l in language_matrix if l[1])
lng2        = frozenset(l[2] for l in language_matrix if l[2])
lng_en_name = frozenset(lng for l in language_matrix
                        for lng in l[3].lower().split('; ') if lng)
lng_fr_name = frozenset(lng for l in language_matrix
                        for lng in l[4].lower().split('; ') if lng)
lng_all_names = lng3 | lng3term | lng2 | lng_en_name | lng_fr_name

lng3_to_lng3term = dict((l[0], l[1]) for l in language_matrix if l[1])
lng3term_to_lng3 = dict((l[1], l[0]) for l in language_matrix if l[1])

lng3_to_lng2 = dict((l[0], l[2]) for l in language_matrix if l[2])
lng2_to_lng3 = dict((l[2], l[0]) for l in language_matrix if l[2])

# we only return the first given english name, hoping it is the most used one
lng3_to_lng_en_name = dict((l[0], l[3].split('; ')[0])
                           for l in language_matrix if l[3])
lng_en_name_to_lng3 = dict((en_name.lower(), l[0])
                           for l in language_matrix if l[3]
                           for en_name in l[3].split('; '))

# we only return the first given french name, hoping it is the most used one
lng3_to_lng_fr_name = dict((l[0], l[4].split('; ')[0])
                           for l in language_matrix if l[4])
lng_fr_name_to_lng3 = dict((fr_name.lower(), l[0])
                           for l in language_matrix if l[4]
                           for fr_name in l[4].split('; '))

# contains a list of exceptions: strings that should be parsed as a language
# but which are not in an ISO form
lng_exceptions = { 'unknown': ('und', None),
                   'inconnu': ('und', None),
                   'unk': ('und', None),
                   'un': ('und', None),
                   'gr': ('gre', None),
                   'greek': ('gre', None),
                   'esp': ('spa', None),
                   'español': ('spa', None),
                   'se': ('swe', None),
                   'po': ('pt', 'br'),
                   'pob': ('pt', 'br'),
                   'br': ('pt', 'br'),
                   'brazilian': ('pt', 'br'),
                   'català': ('cat', None),
                   'cz': ('cze', None),
                   'ua': ('ukr', None),
                   'cn': ('chi', None),
                   'chs': ('chi', None),
                   'jp': ('jpn', None)
                   }


def is_iso_language(language):
    return language.lower() in lng_all_names

def is_language(language):
    return is_iso_language(language) or language in lng_exceptions

def lang_set(languages, strict=False):
    """Return a set of guessit.Language created from their given string
    representation.

    if strict is True, then this will raise an exception if any language
    could not be identified.
    """
    return set(Language(l, strict=strict) for l in languages)


class Language(object):
    """This class represents a human language.

    You can initialize it with pretty much anything, as it knows conversion
    from ISO-639 2-letter and 3-letter codes, English and French names.

    You can also distinguish languages for specific countries, such as
    Portuguese and Brazilian Portuguese.

    >>> Language('fr')
    Language(French)

    >>> Language('eng').french_name
    u'anglais'

    >>> Language('pt(br)').country.english_name
    u'Brazil'

    >>> Language('Español (Latinoamérica)').country.english_name
    u'Latin America'

    >>> Language('Spanish (Latin America)') == Language('Español (Latinoamérica)')
    True

    >>> Language('zz', strict=False).english_name
    u'Unknown'
    """

    _with_country_regexp = re.compile('(.*)\((.*)\)')

    def __init__(self, language, country=None, strict=False):
        language = to_unicode(language.strip().lower())
        with_country = Language._with_country_regexp.match(language)
        if with_country:
            self.lang = Language(with_country.group(1)).lang
            self.country = Country(with_country.group(2))
            return

        self.lang = None
        self.country = Country(country) if country else None

        if len(language) == 2:
            self.lang = lng2_to_lng3.get(language)
        elif len(language) == 3:
            self.lang = (language
                         if language in lng3
                         else lng3term_to_lng3.get(language))
        else:
            self.lang = (lng_en_name_to_lng3.get(language) or
                         lng_fr_name_to_lng3.get(language))

        if self.lang is None and language in lng_exceptions:
            lang, country = lng_exceptions[language]
            self.lang = Language(lang).alpha3
            self.country = Country(country) if country else None

        msg = 'The given string "%s" could not be identified as a language' % language

        if self.lang is None and strict:
            raise ValueError(msg)

        if self.lang is None:
            log.debug(msg)
            self.lang = 'unk'

    @property
    def alpha2(self):
        return lng3_to_lng2[self.lang]

    @property
    def alpha3(self):
        return self.lang

    @property
    def alpha3term(self):
        return lng3_to_lng3term[self.lang]

    @property
    def english_name(self):
        return lng3_to_lng_en_name[self.lang]

    @property
    def french_name(self):
        return lng3_to_lng_fr_name[self.lang]

    def __hash__(self):
        return hash(self.lang)

    def __eq__(self, other):
        if isinstance(other, Language):
            return self.lang == other.lang

        if isinstance(other, basestring):
            try:
                return self == Language(other)
            except ValueError:
                return False

        return False

    def __ne__(self, other):
        return not self == other

    def __nonzero__(self):
        return self.lang != 'unk'

    def __unicode__(self):
        if self.country:
            return '%s(%s)' % (self.english_name, self.country.alpha2)
        else:
            return self.english_name

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __repr__(self):
        if self.country:
            return 'Language(%s, country=%s)' % (self.english_name, self.country)
        else:
            return 'Language(%s)' % self.english_name


ALL_LANGUAGES = frozenset(Language(lng) for lng in lng_all_names) - frozenset([Language('unk')])
ALL_LANGUAGES_NAMES = lng_all_names

def search_language(string, lang_filter=None):
    """Looks for language patterns, and if found return the language object,
    its group span and an associated confidence.

    you can specify a list of allowed languages using the lang_filter argument,
    as in lang_filter = [ 'fr', 'eng', 'spanish' ]

    >>> search_language('movie [en].avi')
    (Language(English), (7, 9), 0.8)

    >>> search_language('the zen fat cat and the gay mad men got a new fan', lang_filter = ['en', 'fr', 'es'])
    (None, None, None)
    """

    # list of common words which could be interpreted as languages, but which
    # are far too common to be able to say they represent a language in the
    # middle of a string (where they most likely carry their commmon meaning)
    lng_common_words = frozenset([
        # english words
        'is', 'it', 'am', 'mad', 'men', 'man', 'run', 'sin', 'st', 'to',
        'no', 'non', 'war', 'min', 'new', 'car', 'day', 'bad', 'bat', 'fan',
        'fry', 'cop', 'zen', 'gay', 'fat', 'cherokee', 'got', 'an', 'as',
        'cat', 'her', 'be', 'hat', 'sun', 'may', 'my', 'mr',
        # french words
        'bas', 'de', 'le', 'son', 'vo', 'vf', 'ne', 'ca', 'ce', 'et', 'que',
        'mal', 'est', 'vol', 'or', 'mon', 'se',
        # spanish words
        'la', 'el', 'del', 'por', 'mar',
        # other
        'ind', 'arw', 'ts', 'ii', 'bin', 'chan', 'ss', 'san', 'oss', 'iii',
        'vi'
        ])
    sep = r'[](){} \._-+'

    if lang_filter:
        lang_filter = lang_set(lang_filter)

    slow = ' %s ' % string.lower()
    confidence = 1.0 # for all of them
    for lang in lng_all_names:

        if lang in lng_common_words:
            continue

        pos = slow.find(lang)

        if pos != -1:
            end = pos + len(lang)
            # make sure our word is always surrounded by separators
            if slow[pos - 1] not in sep or slow[end] not in sep:
                continue

            language = Language(slow[pos:end])
            if lang_filter and language not in lang_filter:
                continue

            # only allow those languages that have a 2-letter code, those who
            # don't are too esoteric and probably false matches
            if language.lang not in lng3_to_lng2:
                continue

            # confidence depends on lng2, lng3, english name, ...
            if len(lang) == 2:
                confidence = 0.8
            elif len(lang) == 3:
                confidence = 0.9
            else:
                # Note: we could either be really confident that we found a
                #       language or assume that full language names are too
                # common words
                confidence = 0.3 # going with the low-confidence route here

            return language, (pos - 1, end - 1), confidence

    return None, None, None
