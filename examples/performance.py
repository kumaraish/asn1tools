from __future__ import print_function

import sys
import timeit

sys.path.insert(0, '..')

import asn1tools

DECODED_MESSAGE = {
    "version": 0,
    "community": b'public',
    "data": {
        "set-request": {
            "request-id": 60,
            "error-status": 0,
            "error-index": 0,
            "variable-bindings": [
                {
                    "name": "1.3.6.1.4.1.253.8.51.10.2.1.7.10.14130101",
                    "value": {
                        "simple": {
                            "string": (b'\x31\x37\x32\x2e\x33\x31'
                                       b'\x2e\x31\x39\x2e\x37\x33')
                        }
                    }
                },
                {
                    "name": "1.3.6.1.4.1.253.8.51.10.2.1.5.10.14130400",
                    "value": {
                        "simple": {
                            "number": 2
                        }
                    }
                },
                {
                    "name": "1.3.6.1.4.1.253.8.51.10.2.1.7.10.14130102",
                    "value": {
                        "simple": {
                            "string": (b'\x32\x35\x35\x2e\x32\x35'
                                       b'\x35\x2e\x32\x35\x35\x2e'
                                       b'\x30')
                        }
                    }
                },
                {
                    "name": "1.3.6.1.4.1.253.8.51.10.2.1.7.10.14130104",
                    "value": {
                        "simple": {
                            "string": (b'\x31\x37\x32\x2e\x33\x31'
                                       b'\x2e\x31\x39\x2e\x32')
                        }
                    }
                }
            ]
        }
    }
}

ENCODED_MESSAGE = (
    b'0\x81\x9f\x02\x01\x00\x04\x06public\xa3\x81\x91\x02'
    b'\x01<\x02\x01\x00\x02\x01\x000\x81\x850"\x06\x12+\x06'
    b'\x01\x04\x01\x81}\x083\n\x02\x01\x07\n\x86\xde\xb75'
    b'\x04\x0c172.31.19.730\x17\x06\x12+\x06\x01\x04\x01\x81'
    b'}\x083\n\x02\x01\x05\n\x86\xde\xb9`\x02\x01\x020#\x06'
    b'\x12+\x06\x01\x04\x01\x81}\x083\n\x02\x01\x07\n\x86\xde'
    b'\xb76\x04\r255.255.255.00!\x06\x12+\x06\x01\x04\x01\x81'
    b'}\x083\n\x02\x01\x07\n\x86\xde\xb78\x04\x0b172.31.19.2'
)

ITERATIONS = 3000


def asn1tools_encode_decode():
    snmp_v1 = asn1tools.compile_file('../tests/files/snmp_v1.asn')

    def encode():
        snmp_v1.encode('Message', DECODED_MESSAGE)

    def decode():
        snmp_v1.decode('Message', ENCODED_MESSAGE)

    encode_time = timeit.timeit(encode, number=ITERATIONS)
    decode_time = timeit.timeit(decode, number=ITERATIONS)

    return encode_time, decode_time


def libsnmp_encode_decode():
    try:
        import libsnmp.rfc1905 as libsnmp_rfc1905

        def decode():
            libsnmp_rfc1905.Message().decode(ENCODED_MESSAGE)

        encode_time = float('nan')
        decode_time = timeit.timeit(decode, number=ITERATIONS)
    except ImportError:
        encode_time = float('nan')
        decode_time = float('nan')
        print('Unable to import libsnmp.')

    return encode_time, decode_time


def asn1crypto_encode_decode():
    try:
        from asn1crypto.core import (Sequence,
                                     SequenceOf,
                                     Choice,
                                     Integer,
                                     ObjectIdentifier,
                                     OctetString)

        class ErrorStatus(Integer):
            _map = {
                0: 'noError',
                1: 'tooBig',
                2: 'noSuchName',
                3: 'badValue',
                4: 'readOnly',
                5: 'genErr'
            }

        class IpAddress(OctetString):
            class_ = 1
            tag = 0

        class Counter(Integer):
            class_ = 1
            tag = 1

        class Gauge(Integer):
            class_ = 1
            tag = 2

        class TimeTicks(Integer):
            class_ = 1
            tag = 3

        class Opaque(OctetString):
            class_ = 1
            tag = 4

        class VarBindChoice(Choice):
            _alternatives = [
                ('number', Integer),
                ('string', OctetString),
                ('object', ObjectIdentifier),
                ('address', IpAddress),
                ('counter', Counter),
                ('gauge', Gauge),
                ('ticks', TimeTicks),
                ('arbitrary', Opaque)
            ]

        class VarBind(Sequence):
            _fields = [
                ('name', ObjectIdentifier),
                ('value', VarBindChoice),
            ]

        class VarBindList(SequenceOf):
            _child_spec = VarBind

        class PDU(Sequence):
            _fields = [
                ('request-id', Integer),
                ('error-status', ErrorStatus),
                ('error-index', Integer),
                ('variable-bindings', VarBindList),
            ]

        class PDUs(Choice):
            _alternatives = [
                ('get-pdu', PDU, {'tag_type': 'implicit', 'tag': 0}),
                ('getnext-pdu', PDU, {'tag_type': 'implicit', 'tag': 1}),
                ('response-pdu', PDU, {'tag_type': 'implicit', 'tag': 2}),
                ('set-pdu', PDU, {'tag_type': 'implicit', 'tag': 3}),
            ]

        class Message(Sequence):
            _fields = [
                ('version', Integer),
                ('community', OctetString),
                ('pdu', PDUs),
            ]

        def decode():
            Message.load(ENCODED_MESSAGE).native

        encode_time = float('nan')
        decode_time = timeit.timeit(decode, number=ITERATIONS)
    except ImportError:
        encode_time = float('nan')
        decode_time = float('nan')
        print('Unable to import asn1crypto.')

    return encode_time, decode_time


asn1tools_encode_time, asn1tools_decode_time = asn1tools_encode_decode()
libsnmp_encode_time, libsnmp_decode_time = libsnmp_encode_decode()
asn1crypto_encode_time, asn1crypto_decode_time = asn1crypto_encode_decode()

# Encode comparsion output.
measurements = [
    ('asn1tools', asn1tools_encode_time),
    ('libsnmp', libsnmp_encode_time),
    ('asn1crypto', asn1crypto_encode_time)
]

measurements = sorted(measurements, key=lambda m: m[1])

print()
print('Encode time of {} iterations:'.format(ITERATIONS))
print()
print('PACKAGE      SECONDS')
for package, seconds in measurements:
    print('{:12s} {:f}'.format(package, seconds))

# Decode comparsion output.
measurements = [
    ('asn1tools', asn1tools_decode_time),
    ('libsnmp', libsnmp_decode_time),
    ('asn1crypto', asn1crypto_decode_time)
]

measurements = sorted(measurements, key=lambda m: m[1])

print()
print('Decode time of {} iterations:'.format(ITERATIONS))
print()
print('PACKAGE      SECONDS')
for package, seconds in measurements:
    print('{:12s} {:f}'.format(package, seconds))