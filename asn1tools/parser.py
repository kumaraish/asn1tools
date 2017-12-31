"""Convert ASN.1 specifications to Python data structures.

"""

import logging
import re

from pyparsing import Literal
from pyparsing import Keyword
from pyparsing import Word
from pyparsing import ZeroOrMore
from pyparsing import Regex
from pyparsing import printables
from pyparsing import delimitedList
from pyparsing import Group
from pyparsing import Optional
from pyparsing import Forward
from pyparsing import StringEnd
from pyparsing import OneOrMore
from pyparsing import nums
from pyparsing import Suppress
from pyparsing import ParseException
from pyparsing import ParseSyntaxException
from pyparsing import NotAny
from pyparsing import NoMatch
from pyparsing import QuotedString
from pyparsing import Combine


LOGGER = logging.getLogger(__name__)


class ParseError(Exception):
    pass


class InternalParserError(Exception):
    pass


def is_parameterized_object_set_assignment(tokens):
    return tokens[0][0].isupper() and tokens[2:4] == ['::=', '{']


def is_parameterized_object_assignment(_):
    return False


def is_parameterized_object_class_assignment(tokens):
    return tokens[0][0].isupper() and tokens[1:3] == ['::=', 'CLASS']


def is_parameterized_type_assignment(tokens):
    return tokens[0][0].isupper()


def is_parameterized_value_assignment(tokens):
    return tokens[0][0].islower()


def convert_number(token):
    if isinstance(token, list):
        token = token[0]

    try:
        return int(token)
    except (ValueError, TypeError):
        return token


def convert_size(tokens):
    if len(tokens) == 0:
        return None

    tokens = tokens[0]

    if tokens[0] != 'SIZE':
        return None

    tokens = tokens[1]

    size = []

    for item_tokens in tokens:
        if '..' in item_tokens:
            value = (convert_number(item_tokens[0]),
                     convert_number(item_tokens[2]))
        else:
            value = convert_number(item_tokens[0])

        size.append(value)

    return size

def convert_table(tokens):
    tokens = tokens[0]

    try:
        if isinstance(tokens[1][0][0], list):
            defined_object_set = tokens[1][0][0][0]
        else:
            defined_object_set = tokens[1][0][0]
    except IndexError:
        return None

    try:
        component_ids = tokens[4]
    except IndexError:
        return defined_object_set

    return [defined_object_set, component_ids]


def convert_enum_values(tokens):
    number = 0
    values = {}

    for token in tokens:
        if len(token) == 2:
            number = int(token[1])

        values[number] = token[0]
        number += 1

    return values


def convert_tag(tokens):
    if len(tokens) > 0:
        if len(tokens[0]) == 1:
            tag = {
                'number': int(tokens[0][0])
            }
        else:
            tag = {
                'number': int(tokens[0][1]),
                'class': tokens[0][0]
            }

        if tokens[1]:
            tag['kind'] = tokens[1][0] if tokens[1] else None

        return tag


def convert_members(tokens):
    members = []

    for member_tokens in tokens:
        if member_tokens in [['...'], '...']:
            member_tokens = [['...', [], ''], []]

        if member_tokens[:2] == ['COMPONENTS', 'OF']:
            continue

        member_tokens, qualifiers = member_tokens
        member = convert_type(member_tokens[2:])
        member['name'] = member_tokens[0]
        member['optional'] = 'OPTIONAL' in qualifiers

        if 'DEFAULT' in qualifiers:
            if len(qualifiers[1]) == 0:
                value = []
            else:
                value = convert_number(qualifiers[1][0])

            member['default'] = value

        tag = convert_tag(member_tokens[1])

        if tag:
            member['tag'] = tag

        members.append(member)

    return members


def convert_type(tokens):
    if tokens[0:2] == ['SEQUENCE', '{']:
        converted_type = {
            'type': 'SEQUENCE',
            'members': convert_members(tokens[2])
        }
    elif tokens[0] == 'SEQUENCE' and tokens[2] == 'OF':
        converted_type = {
            'type': 'SEQUENCE OF',
            'element': convert_type(tokens[4:]),
            'size': convert_size(tokens[1])
        }

        tag = convert_tag(tokens[3])

        if tag:
            converted_type['element']['tag'] = tag
    elif tokens[0:2] == ['SET', '{']:
        converted_type = {
            'type': 'SET',
            'members': convert_members(tokens[2])
        }
    elif tokens[0] == 'SET' and tokens[2] == 'OF':
        converted_type = {
            'type': 'SET OF',
            'element': convert_type(tokens[4:]),
            'size': convert_size(tokens[1])
        }

        tag = convert_tag(tokens[3])

        if tag:
            converted_type['element']['tag'] = tag
    elif tokens[0:2] == ['CHOICE', '{']:
        converted_type = {
            'type': 'CHOICE',
            'members': convert_members(tokens[2])
        }
    elif tokens[0] == 'INTEGER':
        converted_type = {'type': 'INTEGER'}
        restricted_to = []

        if len(tokens) > 2:
            for constraint_tokens in tokens[2]:
                if '..' in constraint_tokens:
                    minimum = convert_number(constraint_tokens[0])
                    maximum = convert_number(constraint_tokens[2])
                    restricted_to.append((minimum, maximum))
                elif len(constraint_tokens) == 1:
                    restricted_to.append(convert_number(constraint_tokens[0]))

            if restricted_to:
                converted_type['restricted-to'] = restricted_to
    elif tokens[0] == 'REAL':
        converted_type = {'type': 'REAL'}
        restricted_to = []

        if len(tokens) > 1:
            for constraint_tokens in tokens[1]:
                if '..' in constraint_tokens:
                    minimum = constraint_tokens[0][0]
                    maximum = constraint_tokens[2][0]
                    restricted_to.append((minimum, maximum))
                elif len(constraint_tokens) == 1:
                    restricted_to.append(constraint_tokens[0][0])

            if restricted_to:
                converted_type['restricted-to'] = restricted_to
    elif tokens[0:2] == ['ENUMERATED', '{']:
        converted_type = {
            'type': 'ENUMERATED',
            'values': convert_enum_values(tokens[2])
        }
    elif tokens[0:1] == ['OBJECT IDENTIFIER']:
        converted_type = {'type': 'OBJECT IDENTIFIER'}
    elif tokens[0:1] == ['BIT STRING']:
        converted_type = {'type': 'BIT STRING',
                          'size': convert_size(tokens[2])}
    elif tokens[0:1] == ['OCTET STRING']:
        converted_type = {'type': 'OCTET STRING',
                          'size': convert_size(tokens[1])}
    elif tokens[0] == 'IA5String':
        converted_type = {'type': 'IA5String'}
    elif tokens[0] == 'ANY DEFINED BY':
        converted_type = {
            'type': 'ANY DEFINED BY',
            'value': tokens[1],
            'choices': {}
        }
    elif '&' in tokens[0]:
        converted_type = {
            'type': tokens[0],
            'table': convert_table(tokens[1:])
        }
    else:
        converted_type = {'type': tokens[0]}

    return converted_type


def convert_parameterized_object_set_assignment(tokens):
    members = []

    try:
        for member_tokens in tokens[4]:
            if len(member_tokens[0]) == 1:
                member = member_tokens[0][0]
            else:
                for item_tokens in member_tokens[0]:
                    member = {}

                    for item_tokens in member_tokens[0]:
                        name = item_tokens[0]
                        value = item_tokens[1]
                        member[name] = convert_number(value)

            members.append(member)
    except IndexError:
        pass

    return {'class': tokens[1], 'members': members}


def convert_parameterized_object_class_assignment(tokens):
    members = []

    for member in tokens[3]:
        if member[0][1].islower():
            type_ = member[1]
        else:
            type_ = 'OpenType'

        members.append({
            'name': member[0],
            'type': type_,
            'optional': False
        })

    return {'members': members}


def convert_parameterized_type_assignment(tokens):
    converted_type = convert_type(tokens[3:])

    try:
        tag = convert_tag(tokens[2])
    except ValueError:
        tag = None

    if tag:
        converted_type['tag'] = tag

    return converted_type


def convert_parameterized_value_assignment(tokens):
    type_ = tokens[1][0]

    if type_ == 'INTEGER':
        value = int(tokens[3][0])
    elif type_ == 'OBJECT IDENTIFIER':
        value = []

        for value_tokens in tokens[3]:
            if len(value_tokens) == 2:
                value.append((value_tokens[0], int(value_tokens[1])))
            else:
                value.append(convert_number(value_tokens[0]))
    elif type_ == 'BOOLEAN':
        value = tokens[3][0]
    elif type_ == 'BIT STRING':
        value = tokens[3][0]
        if value[-1] == 'B':
            value = '0b' + re.sub(r"[\sB']", '', value)
        else:
            value = '0x' + re.sub(r"[\sH']", '', value)
    else:
        value = tokens[3]

    return {'type': type_, 'value': value}


def create_grammar():
    """Return the ASN.1 grammar as Pyparsing objects.

    """

    # Keywords.
    SEQUENCE = Keyword('SEQUENCE').setName('SEQUENCE')
    CHOICE = Keyword('CHOICE').setName('CHOICE')
    ENUMERATED = Keyword('ENUMERATED').setName('ENUMERATED')
    DEFINITIONS = Keyword('DEFINITIONS').setName('DEFINITIONS')
    BEGIN = Keyword('BEGIN').setName('BEGIN')
    END = Keyword('END').setName('END')
    AUTOMATIC = Keyword('AUTOMATIC').setName('AUTOMATIC')
    TAGS = Keyword('TAGS').setName('TAGS')
    OPTIONAL = Keyword('OPTIONAL').setName('OPTIONAL')
    OF = Keyword('OF').setName('OF')
    SIZE = Keyword('SIZE').setName('SIZE')
    INTEGER = Keyword('INTEGER').setName('INTEGER')
    REAL = Keyword('REAL').setName('REAL')
    BIT_STRING = Keyword('BIT STRING').setName('BIT STRING')
    OCTET_STRING = Keyword('OCTET STRING').setName('OCTET STRING')
    DEFAULT = Keyword('DEFAULT').setName('DEFAULT')
    IMPORTS = Keyword('IMPORTS').setName('IMPORTS')
    EXPORTS = Keyword('EXPORTS').setName('EXPORTS')
    FROM = Keyword('FROM').setName('FROM')
    CONTAINING = Keyword('CONTAINING').setName('CONTAINING')
    IMPLICIT = Keyword('IMPLICIT').setName('IMPLICIT')
    EXPLICIT = Keyword('EXPLICIT').setName('EXPLICIT')
    OBJECT_IDENTIFIER = Keyword('OBJECT IDENTIFIER').setName('OBJECT IDENTIFIER')
    APPLICATION = Keyword('APPLICATION').setName('APPLICATION')
    PRIVATE = Keyword('PRIVATE').setName('PRIVATE')
    SET = Keyword('SET').setName('SET')
    ANY_DEFINED_BY = Keyword('ANY DEFINED BY').setName('ANY DEFINED BY')
    EXTENSIBILITY = Keyword('EXTENSIBILITY').setName('EXTENSIBILITY')
    IMPLIED = Keyword('IMPLIED').setName('IMPLIED')
    BOOLEAN = Keyword('BOOLEAN').setName('BOOLEAN')
    TRUE = Keyword('TRUE').setName('TRUE')
    FALSE = Keyword('FALSE').setName('FALSE')
    CLASS = Keyword('CLASS').setName('CLASS')
    WITH = Keyword('WITH').setName('WITH')
    SYNTAX = Keyword('SYNTAX').setName('SYNTAX')
    UNIQUE = Keyword('UNIQUE').setName('UNIQUE')
    NULL = Keyword('NULL').setName('NULL')
    COMPONENT = Keyword('COMPONENT').setName('COMPONENT')
    COMPONENTS = Keyword('COMPONENTS').setName('COMPONENTS')
    PRESENT = Keyword('PRESENT').setName('PRESENT')
    ABSENT = Keyword('ABSENT').setName('ABSENT')
    ALL = Keyword('ALL').setName('ALL')
    MIN = Keyword('MIN').setName('MIN')
    MAX = Keyword('MAX').setName('MAX')
    INCLUDES = Keyword('INCLUDES').setName('INCLUDES')
    PATTERN = Keyword('PATTERN').setName('PATTERN')
    CONSTRAINED_BY = Keyword('CONSTRAINED BY').setName('CONSTRAINED BY')
    UNION = Keyword('UNION').setName('UNION')
    INTERSECTION = Keyword('INTERSECTION').setName('INTERSECTION')

    # Various literals.
    word = Word(printables, excludeChars=',(){}[].:=;"|').setName('word')
    identifier = Regex(r'[a-z][a-zA-Z0-9-]*').setName('identifier')
    assign = Literal('::=').setName('::=')
    left_parenthesis = Literal('(')
    right_parenthesis = Literal(')')
    left_brace = Literal('{')
    right_brace = Literal('}')
    left_bracket = Literal('[')
    right_bracket = Literal(']')
    left_version_brackets = Literal('[[')
    right_version_brackets = Literal(']]')
    colon = Literal(':')
    semi_colon = Literal(';')
    dot = Literal('.')
    range_separator = Literal('..')
    ellipsis = Literal('...')
    pipe = Literal('|')
    caret = Literal('^')
    comma = Literal(',')
    at = Literal('@')
    integer = Word(nums)
    real_number = Regex(r'[+-]?\d+\.?\d*([eE][+-]?\d+)?')
    bstring = Regex(r"'[01\s]*'B")
    hstring = Regex(r"'[0-9A-F\s]*'H")
    cstring = QuotedString('"')
    number = word
    ampersand = Literal('&')
    less_than = Literal('<')

    # Forward declarations.
    value = Forward()
    type_ = Forward()
    object_ = Forward()
    object_set = Forward()
    primitive_field_name = Forward()
    constraint = Forward()
    element_set_spec = Forward()
    token_or_group_spec = Forward()
    value_reference = Forward().setName('valuereference')
    type_reference = Forward().setName('typereference')
    value_set = Forward().setName('"valueSet" not implemented')
    named_type = Forward()
    root_element_set_spec = Forward()
    defined_object_set = Forward()
    syntax_list = Forward()
    object_from_object = Forward()
    object_set_from_objects = Forward()
    defined_value = Forward()
    component_type_lists = Forward()
    extension_and_exception = Forward()
    optional_extension_marker = Forward()
    additional_element_set_spec = Forward()
    reference = Forward()
    defined_object_class = Forward()
    defined_type = Forward()
    module_reference = Forward()
    external_type_reference = Forward()
    external_value_reference = Forward()
    simple_defined_type = Forward()
    defined_object = Forward()
    referenced_value = Forward()
    builtin_value = Forward()
    named_value = Forward()
    sequence_value = Forward()
    signed_number = Forward()
    name_and_number_form = Forward()
    number_form = Forward().setName('numberForm')
    definitive_number_form = Forward().setName('definitiveNumberForm')

    value_field_reference = Combine(ampersand + value_reference)
    type_field_reference = Combine(ampersand + type_reference)

    range_ = (word + range_separator + word)

    size = Group(SIZE
                 + Group(Suppress(left_parenthesis)
                         + Group(delimitedList(range_ | word, delim=pipe))
                         + Suppress(right_parenthesis)))

    size_paren = (Suppress(Optional(left_parenthesis))
                  + size
                  + Suppress(Optional(right_parenthesis)))

    tag = Group(Optional(Suppress(left_bracket)
                         + Group(Optional(APPLICATION | PRIVATE) + word)
                         + Suppress(right_bracket)
                         + Group(Optional(IMPLICIT | EXPLICIT))))

    any_defined_by_type = (ANY_DEFINED_BY + word)
    any_defined_by_type.setName('ANY DEFINED BY')

    identifier_list = delimitedList(identifier)

    # X.683: 8. Parameterized assignments
    dummy_reference = reference
    dummy_governor = dummy_reference
    governor = (type_ | defined_object_class)
    param_governor = (governor | dummy_governor)
    parameter = (Optional(param_governor + colon) + dummy_reference)
    parameter_list = Suppress(Optional(left_brace
                                       + delimitedList(parameter)
                                       + right_brace))

    # X.683: 9. Referencing parameterized definitions
    actual_parameter = Group(type_
                             | value
                             | value_set
                             | defined_object_class
                             | object_
                             | object_set)
    actual_parameter_list = Group(Suppress(left_brace)
                                  + delimitedList(actual_parameter)
                                  + Suppress(right_brace))
    parameterized_object = (defined_object + actual_parameter_list)
    parameterized_object_set = (defined_object_set + actual_parameter_list)
    parameterized_object_class = (defined_object_class + actual_parameter_list)
    parameterized_value_set_type = (simple_defined_type
                                    + actual_parameter_list)
    simple_defined_value = (external_value_reference
                            | value_reference)
    parameterized_value = (simple_defined_value
                           + actual_parameter_list)
    simple_defined_type <<= (external_type_reference
                             | type_reference)
    parameterized_type = (simple_defined_type
                          + actual_parameter_list)
    parameterized_reference = (reference + Optional(left_brace + right_brace))

    # X.682: 11. Contents constraints
    contents_constraint = NoMatch().setName('"contentsConstraint" not implemented')

    # X.682: 10. Table constraints, including component relation constraints
    level = OneOrMore(dot)
    component_id_list = identifier
    at_notation = (Suppress(at)
                   - (component_id_list
                      | Combine(level + component_id_list)))
    component_relation_constraint = (left_brace
                                     + Group(Group(defined_object_set))
                                     + right_brace
                                     + left_brace
                                     - Group(delimitedList(at_notation))
                                     - right_brace)
    simple_table_constraint = object_set
    table_constraint = (component_relation_constraint
                        | simple_table_constraint)

    # X.682: 9. User-defined constants
    user_defined_constraint_parameter = ((governor
                                          + colon
                                          + (value
                                             | value_set
                                             | object_
                                             | object_set))
                                         | type_
                                         | defined_object_class)
    user_defined_constraint = (CONSTRAINED_BY
                               - left_brace
                               - Optional(delimitedList(user_defined_constraint_parameter))
                               - right_brace)

    # X.682: 8. General constraint specification
    general_constraint = (user_defined_constraint
                          | table_constraint
                          | contents_constraint)

    # X.681: 7. ASN.1 lexical items
    object_set_reference = type_reference
    value_set_field_reference = NoMatch().setName('"valueSetFieldReference" not implemented')
    object_field_reference = NoMatch().setName('"objectFieldReference" not implemented')
    object_set_field_reference = NoMatch().setName('"objectSetFieldReference" not implemented')
    object_class_reference = type_reference
    object_reference = value_reference

    # X.681: 8. Referencing definitions
    external_object_set_reference = NoMatch().setName('"externalObjectSetReference" not implemented')
    defined_object_set <<= (external_object_set_reference
                            | object_set_reference)
    defined_object <<= NoMatch().setName('"definedObject" not implemented')
    defined_object_class <<= object_class_reference

    # X.681: 9. Information object class definition and assignment
    field_name = primitive_field_name
    primitive_field_name <<= (type_field_reference
                              | value_field_reference
                              | value_set_field_reference
                              | object_field_reference
                              | object_set_field_reference)
    object_set_field_spec = NoMatch().setName('"objectSetFieldSpec" not implemented')
    object_field_spec = NoMatch().setName('"objectFieldSpec" not implemented')
    variable_type_value_set_field_spec = NoMatch().setName(
        '"variableTypeValueSetFieldSpec" not implemented')
    fixed_type_value_set_field_spec = NoMatch().setName('"fixedTypeValueSetFieldSpec" not implemented')
    variable_type_value_field_spec = NoMatch().setName('"variableTypeValueFieldSpec" not implemented')
    fixed_type_value_field_spec = (value_field_reference
                                   + type_
                                   + Optional(UNIQUE)
                                   + Optional(OPTIONAL
                                              | (DEFAULT - value)))
    type_field_spec = (type_field_reference
                       + Optional(OPTIONAL
                                  | (DEFAULT - type_)))
    field_spec = Group(type_field_spec
                       | fixed_type_value_field_spec
                       | variable_type_value_field_spec
                       | fixed_type_value_set_field_spec
                       | variable_type_value_set_field_spec
                       | object_field_spec
                       | object_set_field_spec)
    with_syntax_spec = (WITH - SYNTAX - syntax_list)
    object_class_defn = (CLASS
                         - Suppress(left_brace)
                         - Group(delimitedList(field_spec))
                         - Suppress(right_brace)
                         - Optional(with_syntax_spec))
    object_class = (object_class_defn
                    # | defined_object_class
                    | parameterized_object_class)
    parameterized_object_class_assignment = (object_class_reference
                                             + parameter_list
                                             + assign
                                             + object_class)

    # X.681: 10. Syntax list
    literal = (word | comma)
    required_token = (literal | primitive_field_name)
    optional_group = (left_bracket
                      + OneOrMore(token_or_group_spec)
                      + right_bracket)
    token_or_group_spec <<= (required_token | optional_group)
    syntax_list <<= (left_brace
                     + OneOrMore(token_or_group_spec)
                     + right_brace)

    # X.681: 11. Information object definition and assignment
    setting = (type_ | value | value_set | object_ | object_set | QuotedString('"'))
    field_setting =  Group(primitive_field_name + setting)
    default_syntax = (Suppress(left_brace)
                      + delimitedList(field_setting)
                      + Suppress(right_brace))
    defined_syntax = NoMatch().setName('"definedSyntax" not implemented')
    object_defn = Group(default_syntax | defined_syntax)
    object_ <<= (defined_object
                 | object_defn
                 | object_from_object
                 | parameterized_object)
    parameterized_object_assignment = (object_reference
                                       + parameter_list
                                       + Group(defined_object_class)
                                       + assign
                                       + object_)

    # X.681: 12. Information object set definition and assignment
    object_set_elements = (object_
                           | defined_object_set
                           | object_set_from_objects
                           | parameterized_object_set)
    object_set_spec = ((root_element_set_spec
                        + Optional(comma
                                   + ellipsis
                                   + Optional(comma
                                              + additional_element_set_spec)))
                       | (ellipsis + Optional(comma + additional_element_set_spec)))
    object_set <<= (left_brace + Group(object_set_spec) + right_brace)
    parameterized_object_set_assignment = (object_set_reference
                                           + parameter_list
                                           + defined_object_class
                                           - assign
                                           - object_set)

    # X.681: 13. Associated tables

    # X.681: 14. Notation for the object class field type
    fixed_type_field_val = (builtin_value | referenced_value)
    open_type_field_val = (type_ + colon + value)
    object_class_field_value = (open_type_field_val
                                | fixed_type_field_val)
    object_class_field_type = Combine(defined_object_class
                                      + dot
                                      + field_name)
    object_class_field_type.setName('ObjectClassFieldType')

    # X.681: 15. Information from objects
    object_set_from_objects <<= NoMatch().setName('"objectSetFromObjects" not implemented')
    object_from_object <<= NoMatch().setName('"objectFromObject" not implemented')

    # X.680: 49. The exception identifier
    exception_spec = NoMatch().setName('"exceptionSpec" not implemented')

    # X.680: 47. Subtype elements
    pattern_constraint = (PATTERN + value)
    value_constraint = constraint
    presence_constraint = (PRESENT | ABSENT | OPTIONAL)
    component_constraint = Optional(value_constraint | presence_constraint)
    named_constraint = (identifier + component_constraint)
    type_constraints = delimitedList(named_constraint)
    full_specification = (left_brace + type_constraints + right_brace)
    partial_specification = (left_brace + ellipsis + comma + type_constraints + right_brace)
    single_type_constraint = constraint
    multiple_type_constraints = (full_specification | partial_specification)
    inner_type_constraints = ((WITH + COMPONENT + single_type_constraint)
                              | (WITH + COMPONENTS + multiple_type_constraints))
    permitted_alphabet = Suppress(FROM - constraint)
    type_constraint = type_
    size_constraint = (SIZE + Group(constraint))
    upper_end_value = (value | MAX)
    lower_end_value = (value | MIN)
    upper_endpoint = (Optional(less_than) + upper_end_value)
    lower_endpoint = (lower_end_value + Optional(less_than))
    value_range = (lower_endpoint + range_separator - upper_endpoint)
    contained_subtype = (Optional(INCLUDES) + type_)
    single_value = value
    subtype_elements = (size_constraint
                        | permitted_alphabet
                        | value_range
                        | inner_type_constraints
                        | single_value
                        | pattern_constraint
                        | contained_subtype
                        | type_constraint)

    # X.680: 46. Element set specification
    union_mark = (pipe | UNION)
    intersection_mark = (caret | INTERSECTION)
    elements = Group(subtype_elements
                     | object_set_elements
                     | (left_parenthesis + element_set_spec + right_parenthesis))
    unions = delimitedList(elements, delim=(union_mark | intersection_mark))
    element_set_spec <<= unions
    root_element_set_spec <<= element_set_spec
    additional_element_set_spec <<= element_set_spec
    element_set_specs = (root_element_set_spec
                         + Optional(Suppress(comma - ellipsis)
                                    + Optional(Suppress(comma)
                                               - additional_element_set_spec)))

    # X.680: 45. Constrained types
    subtype_constraint = element_set_specs
    constraint_spec = (general_constraint
                       | subtype_constraint)
    constraint <<= (Suppress(left_parenthesis)
                    - constraint_spec
                    - Suppress(right_parenthesis))

    # X.680: 40. Definition of unrestricted character string types
    unrestricted_character_string_value = NoMatch().setName(
        '"unrestrictedCharacterStringValue" not implemented')

    # X.680: 39. Canonical order of characters

    # X.680: 38. Specification of the ASN.1 module "ASN.1-CHARACTER-MODULE"

    # X.680: 37. Definition of restricted character string types
    group = number
    plane = number
    row = number
    cell = number
    quadruple = (left_brace
                 + group + comma
                 + plane + comma
                 + row + comma +
                 cell
                 + right_brace)
    table_column = number
    table_row = number
    tuple_ = (left_brace + table_column + comma + table_row + right_brace)
    charsyms = NoMatch().setName('"charsyms" not implemented')
    character_string_list = (left_brace + charsyms + right_brace)
    restricted_character_string_value = (cstring
                                         | character_string_list
                                         | quadruple
                                         | tuple_)

    # X.680: 36. Notation for character string types
    character_string_value = (restricted_character_string_value
                              | unrestricted_character_string_value)

    # X.680: 35. The character string types

    # X.680: 34. Notation for the external type
    external_value = sequence_value

    # X.680: 33. Notation for embedded-pdv type
    embedded_pdv_value = sequence_value

    # X.680: 32. Notation for relative object identifier type
    relative_oid_components = Group(number_form
                                    | name_and_number_form
                                    | defined_value)
    relative_oid_component_list = OneOrMore(relative_oid_components)
    relative_oid_value = (Suppress(left_brace)
                          + relative_oid_component_list
                          + Suppress(right_brace))

    # X.680: 31. Notation for object identifier type
    name_and_number_form <<= (identifier
                              + Suppress(left_parenthesis)
                              - number_form
                              - Suppress(right_parenthesis))
    number_form <<= (number | defined_value)
    name_form = identifier
    obj_id_components = Group(name_and_number_form
                              | defined_value
                              | number_form
                              | name_form)
    obj_id_components_list = OneOrMore(obj_id_components)
    object_identifier_value = ((Suppress(left_brace)
                                + obj_id_components_list
                                + Suppress(right_brace))
                               | (Suppress(left_brace)
                                  + defined_value
                                  + obj_id_components_list
                                  + Suppress(right_brace)))

    object_identifier_type = (OBJECT_IDENTIFIER
                              + Optional(left_parenthesis
                                         + delimitedList(word, delim='|')
                                         + right_parenthesis))
    object_identifier_type.setName('OBJECT IDENTIFIER')

    # X.680: 30. Notation for tagged types
    tagged_value = NoMatch()

    # X.680: 29. Notation for selection types

    # X.680: 28. Notation for the choice types
    choice_type = (CHOICE
                   - left_brace
                   + Group(Optional(delimitedList(
                       Group(Group(identifier
                                   - tag
                                   - type_)
                             + Group(Optional(OPTIONAL)
                                     + Optional(DEFAULT + word))
                             | ellipsis))))
                   - right_brace)
    choice_type.setName('CHOICE')
    choice_value = (identifier + colon + value)

    # X.680: 27. Notation for the set-of types
    set_of_value = NoMatch()
    set_of_type = (SET
                   + Group(Optional(size))
                   + OF
                   + Optional(Suppress(identifier))
                   - tag
                   - type_)
    set_of_type.setName('SET OF')

    # X.680: 26. Notation for the set types
    set_value = NoMatch()
    set_type = (SET
                - left_brace
                + Group(Optional(component_type_lists
                                 | (extension_and_exception
                                    + optional_extension_marker)))
                - right_brace)
    set_type.setName('SET')

    # X.680: 25. Notation for the sequence-of types
    sequence_of_value = NoMatch()
    sequence_of_type = (SEQUENCE
                        + Group(Optional(size_paren))
                        + OF
                        + Optional(Suppress(identifier))
                        - tag
                        - type_)
    sequence_of_type.setName('SEQUENCE OF')

    # X.680: 24. Notation for the sequence types
    component_value_list = delimitedList(named_value)
    sequence_value <<= (left_brace
                        + Optional(component_value_list)
                        + right_brace)
    component_type = Group(named_type
                           + Group(Optional(OPTIONAL
                                            | (DEFAULT + value)))
                           | (COMPONENTS + OF + type_))
    version_number = (number + Suppress(colon))
    extension_addition_group = (Suppress(left_version_brackets)
                                + Suppress(Group(Optional(version_number)))
                                + delimitedList(component_type)
                                + Suppress(right_version_brackets))
    extension_and_exception <<= (ellipsis + Optional(exception_spec))
    extension_addition = (component_type | extension_addition_group)
    extension_addition_list = delimitedList(extension_addition)
    extension_additions = Optional(Suppress(comma) + extension_addition_list)
    extension_end_marker = (Suppress(comma) + ellipsis)
    optional_extension_marker <<= Optional(Suppress(comma) + ellipsis)
    component_type_list = delimitedList(component_type)
    root_component_type_list = component_type_list
    component_type_lists <<= ((root_component_type_list
                               + Optional(Suppress(comma)
                                          + extension_and_exception
                                          + extension_additions
                                          + ((extension_end_marker
                                              + Suppress(comma)
                                              + root_component_type_list)
                                             | optional_extension_marker)))
                              | (extension_and_exception
                                 + extension_additions
                                 + ((extension_end_marker
                                     + Suppress(comma)
                                     + root_component_type_list)
                                    | optional_extension_marker)))
    sequence_type = (SEQUENCE
                     - left_brace
                     + Group(Optional(component_type_lists
                                    | (extension_and_exception
                                       + optional_extension_marker)))
                     - right_brace)
    sequence_type.setName('SEQUENCE')

    # X.680: 23. Notation for the null type
    null_value = NULL
    null_type = NULL

    # X.680: 22. Notation for the octetstring type
    octet_string_value = (bstring
                          | hstring
                          | (CONTAINING + value))
    octet_string_type = OCTET_STRING
    octet_string_type.setName('OCTET STRING')

    # X.680: 21. Notation for the bitstring type
    bit_string_type = (BIT_STRING
                       + Group(Optional(left_brace
                                        + Group(delimitedList(word
                                                              + left_parenthesis
                                                              + word
                                                              + right_parenthesis))
                                        + right_brace)))
    bit_string_type.setName('BIT STRING')
    bit_string_value = (bstring
                        | hstring
                        | (Suppress(left_brace)
                           + Optional(identifier_list)
                           + Suppress(right_brace))
                        | (CONTAINING - value))

    # X.680: 20. Notation for the real type
    real_value = NoMatch()
    real_type = (REAL
                 + Group(Optional(Group(Suppress(left_parenthesis)
                                        + ((Group(Combine(integer + dot)) + range_separator)
                                           | (Group(integer) + range_separator)
                                           | (Group(real_number) + range_separator))
                                        + Group(real_number)
                                        + Suppress(right_parenthesis)))))
    real_type.setName('REAL')

    # X.680: 19. Notation for the enumerated type
    enumerated_value = identifier
    enumerated_type = (ENUMERATED
                       - left_brace
                       + Group(delimitedList(Group((word
                                                    + Optional(Suppress(left_parenthesis)
                                                               + word
                                                               + Suppress(right_parenthesis)))
                                                   | ellipsis)))
                       - right_brace)
    enumerated_type.setName('ENUMERATED')

    # X.680: 18. Notation for the integer type
    integer_value = (signed_number | identifier)
    signed_number <<= number
    named_number = (identifier
                    + left_parenthesis
                    + (signed_number | defined_value)
                    + right_parenthesis)
    named_number_list = delimitedList(named_number)
    integer_type = (INTEGER
                    + Group(Optional(left_brace
                                     + named_number_list
                                     + right_brace)))
    integer_type.setName('INTEGER')

    # X.680: 17. Notation for boolean type
    boolean_type = BOOLEAN
    boolean_value = (TRUE | FALSE)

    # X.680: 16. Definition of types and values
    named_value <<= (identifier + value)
    referenced_value <<= NoMatch().setName('"referencedValue" not implemented')
    builtin_value <<= (bit_string_value
                       | boolean_value
                       | character_string_value
                       | choice_value
                       | relative_oid_value
                       | sequence_value
                       # | embedded_pdv_value
                       | enumerated_value
                       # | external_value
                       # | instance_of_value
                       | integer_value
                       | null_value
                       | object_identifier_value
                       # | octet_string_value
                       | real_value
                       | sequence_of_value
                       # | set_value
                       # | set_of_value
                       | tagged_value)
    value <<= Group(object_class_field_value)
                    # | referenced_value
                    # | builtin_value)
    named_type <<= Group(identifier
                         - tag
                         - type_)
    referenced_type = defined_type
    referenced_type.setName('ReferencedType')
    builtin_type = (choice_type
                    | integer_type
                    | null_type
                    | real_type
                    | bit_string_type
                    | octet_string_type
                    | enumerated_type
                    | sequence_of_type
                    | sequence_type
                    | object_class_field_type
                    | set_of_type
                    | set_type
                    | object_identifier_type
                    | boolean_type)
    type_ <<= ((builtin_type
                | any_defined_by_type
                | referenced_type)
               + Group(Optional(constraint)))

    # X.680: 15. Assigning types and values
    type_reference <<= (NotAny(END
                               | SEQUENCE
                               | ENUMERATED)
                        + Regex(r'[A-Z][a-zA-Z0-9-]*'))
    value_reference <<= Regex(r'[a-z][a-zA-Z0-9-]*')
    value_set <<= NoMatch().setName('"valueSet" not implemented')
    parameterized_type_assignment = (type_reference
                                     + parameter_list
                                     - assign
                                     - tag
                                     - type_)
    parameterized_value_assignment = (value_reference
                                      + parameter_list
                                      - Group(INTEGER
                                              | type_)
                                      - assign
                                      - value)

    # X.680: 14. Notation to support references to ASN.1 components

    # X.680: 13. Referencing type and value definitions
    external_value_reference <<= (module_reference
                                  + dot
                                  + value_reference)
    external_type_reference <<= (module_reference
                                 + dot
                                 + type_reference)
    defined_type <<= (external_type_reference
                      | parameterized_type
                      | parameterized_value_set_type
                      | type_reference)
    defined_value <<= (external_value_reference
                       | parameterized_value
                       | value_reference)

    # X.680: 12. Module definition
    module_reference <<= word
    assigned_identifier = Suppress(Optional(object_identifier_value
                                            | (defined_value + ~comma)))
    global_module_reference = (module_reference + assigned_identifier)
    reference <<= (type_reference
                   | value_reference
                   | object_class_reference
                   | object_reference
                   | object_set_reference)
    symbol = (parameterized_reference
              | reference)
    symbol_list = Group(delimitedList(symbol))
    symbols_from_module = (symbol_list
                           + FROM
                           + global_module_reference)
    symbols_imported = OneOrMore(Group(symbols_from_module))
    imports = Group(Optional(IMPORTS
                             - symbols_imported
                             - semi_colon))
    symbols_exported = OneOrMore(symbol_list)
    exports = Suppress(Group(Optional(EXPORTS
                                      - (ALL
                                         | (symbols_exported + semi_colon)))))
    assignment = Group(parameterized_object_set_assignment
                       | parameterized_object_assignment
                       | parameterized_object_class_assignment
                       | parameterized_type_assignment
                       | parameterized_value_assignment)
    assignment_list = Group(ZeroOrMore(assignment))
    module_body = (exports + imports + assignment_list)
    definitive_name_and_number_form = (identifier
                                       + Suppress(left_parenthesis)
                                       - definitive_number_form
                                       - Suppress(right_parenthesis))
    definitive_number_form <<= number
    definitive_obj_id_component = Group(definitive_name_and_number_form
                                        | name_form
                                        | definitive_number_form)
    definitive_obj_id_components_list = OneOrMore(definitive_obj_id_component)
    definitive_identifier = Group(Optional(Suppress(left_brace)
                                           - definitive_obj_id_components_list
                                           - Suppress(right_brace)))
    module_identifier = (module_reference
                         + definitive_identifier)
    tag_default = Group(Optional((AUTOMATIC | EXPLICIT | IMPLICIT) + TAGS))
    extension_default = Group(Optional(EXTENSIBILITY + IMPLIED))
    module_definition = Group(Group(module_identifier
                                    - DEFINITIONS
                                    + tag_default
                                    + extension_default
                                    - assign
                                    - BEGIN)
                              + module_body
                              - END)

    # The whole specification.
    specification = OneOrMore(module_definition) + StringEnd()
    comment = (Regex(r"--[\s\S]*?(--|\n)") | Regex(r"--(?:\\\n|[^\n])*"))
    specification.ignore(comment)

    return specification


def parse_string(string):
    """Parse given ASN.1 specification string and return a dictionary of
    its contents.

    >>> with open('foo.asn') as fin:
    ...     foo = asn1tools.parse_string(fin.read())

    """

    grammar = create_grammar()

    try:
        tokens = grammar.parseString(string).asList()
    except (ParseException, ParseSyntaxException) as e:
        raise ParseError("Invalid ASN.1 syntax at line {}, column {}: '{}': {}.".format(
            e.lineno,
            e.column,
            e.markInputline(),
            e.msg))

    modules = {}

    for module in tokens:
        module_name = module[0][0]

        LOGGER.debug("Converting module '%s'.", module_name)

        imports = {}
        types = {}
        values = {}
        object_classes = {}
        object_sets = {}

        imports_tokens = module[1]

        if imports_tokens:
            for from_tokens in imports_tokens[1:-1]:
                from_name = from_tokens[2]
                LOGGER.debug("Converting imports from '%s'.", from_name)
                imports[from_name] = from_tokens[0]

        assignment_tokens = module[2]

        for assignment in assignment_tokens:
            name = assignment[0]

            LOGGER.debug("Converting assignment tokens '%s'.", assignment)

            if is_parameterized_object_set_assignment(assignment):
                LOGGER.debug("Converting object set '%s'.", name)
                value = convert_parameterized_object_set_assignment(assignment)
                LOGGER.debug("Converted object set '%s' to %s.", name, value)
                object_sets[name] = value
            elif is_parameterized_object_assignment(assignment):
                pass
            elif is_parameterized_object_class_assignment(assignment):
                LOGGER.debug("Converting object class '%s'.", name)
                value = convert_parameterized_object_class_assignment(assignment)
                LOGGER.debug("Converted object class '%s' to %s.", name, value)
                object_classes[name] = value
            elif is_parameterized_type_assignment(assignment):
                LOGGER.debug("Converting type '%s'.", name)
                value = convert_parameterized_type_assignment(assignment)
                LOGGER.debug("Converted type '%s' to %s.", name, value)
                types[name] = value
            elif is_parameterized_value_assignment(assignment):
                LOGGER.debug("Converting value '%s'.", name)
                value = convert_parameterized_value_assignment(assignment)
                LOGGER.debug("Converted value '%s' to %s.", name, value)
                values[name] = value
            else:
                raise InternalParserError(
                    'Unrecognized assignment tokens {}.'.format(assignment))

        modules[module_name] = {
            'imports': imports,
            'types': types,
            'values': values,
            'object-classes': object_classes,
            'object-sets': object_sets
        }

        if module[0][3]:
            modules[module_name]['tags'] = module[0][3][0]

        modules[module_name]['extensibility-implied'] = (module[0][4] != [])

    return modules


def parse_files(filenames):
    """Parse given ASN.1 specification file(s) and return a dictionary of
    its/their contents.

    >>> foo = asn1tools.parse_files('foo.asn')

    """

    if isinstance(filenames, str):
        filenames = [filenames]

    string = ''

    for filename in filenames:
        with open(filename, 'r') as fin:
            string += fin.read()
            string += '\n'

    return parse_string(string)
