import {
    CSourceA,
    CSourceB,
    Encoder,
    Decoder
} from './programming_types';

test('bytes', () => {
    var decoded = new Uint8Array([5, 4, 3]);
    var encoded = new Uint8Array([5, 4, 3]);

    var encoder = new Encoder();
    encoder.append_bytes(decoded);
    expect(encoder.toUint8Array()).toEqual(encoded);

    var decoder = new Decoder(encoded);
    expect(decoder.read_bytes(3)).toEqual(decoded);
});

test('uint8', () => {
    var decoded = 5
    var encoded = new Uint8Array([5]);

    var encoder = new Encoder();
    encoder.append_uint8(decoded);
    expect(encoder.toUint8Array()).toEqual(encoded);

    var decoder = new Decoder(encoded);
    expect(decoder.read_uint8()).toEqual(decoded);
});

test('uint16', () => {
    var decoded = 6
    var encoded = new Uint8Array([0, 6]);

    var encoder = new Encoder();
    encoder.append_uint16(decoded);
    expect(encoder.toUint8Array()).toEqual(encoded);

    var decoder = new Decoder(encoded);
    expect(decoder.read_uint16()).toEqual(decoded);
});

test('uint32', () => {
    var decoded_1 = 7;
    var decoded_2 = 0xffffffff;
    var encoded = new Uint8Array([0, 0, 0, 7, 255, 255, 255, 255]);

    var encoder = new Encoder();
    encoder.append_uint32(decoded_1);
    encoder.append_uint32(decoded_2);
    expect(encoder.toUint8Array()).toEqual(encoded);

    var decoder = new Decoder(encoded);
    expect(decoder.read_uint32()).toEqual(decoded_1);
    expect(decoder.read_uint32()).toEqual(decoded_2);
});

test('int8', () => {
    var decoded_1 = 5;
    var decoded_2 = -5;
    var encoded = new Uint8Array([5, 251]);

    var encoder = new Encoder();
    encoder.append_int8(decoded_1);
    encoder.append_int8(decoded_2);
    expect(encoder.toUint8Array()).toEqual(encoded);

    var decoder = new Decoder(encoded);
    expect(decoder.read_int8()).toEqual(decoded_1);
    expect(decoder.read_int8()).toEqual(decoded_2);
});

test('int16', () => {
    var decoded_1 = 6;
    var decoded_2 = -6;
    var encoded = new Uint8Array([0, 6, 255, 250]);

    var encoder = new Encoder();
    encoder.append_int16(decoded_1);
    encoder.append_int16(decoded_2);
    expect(encoder.toUint8Array()).toEqual(encoded);

    var decoder = new Decoder(encoded);
    expect(decoder.read_int16()).toEqual(decoded_1);
    expect(decoder.read_int16()).toEqual(decoded_2);
});

test('int32', () => {
    var decoded_1 = 7;
    var decoded_2 = -7;
    var encoded = new Uint8Array([0, 0, 0, 7, 255, 255, 255, 249]);

    var encoder = new Encoder();
    encoder.append_int32(decoded_1);
    encoder.append_int32(decoded_2);
    expect(encoder.toUint8Array()).toEqual(encoded);

    var decoder = new Decoder(encoded);
    expect(decoder.read_int32()).toEqual(decoded_1);
    expect(decoder.read_int32()).toEqual(decoded_2);
});

test('uint', () => {
    var decoded_1 = 8;
    var decoded_2 = 9;
    var decoded_3 = 10;
    var decoded_4 = 11;
    var encoded = new Uint8Array([8, 0, 9, 0, 0, 10, 0, 0, 0, 11]);

    var encoder = new Encoder();
    encoder.append_uint(decoded_1, 1);
    encoder.append_uint(decoded_2, 2);
    encoder.append_uint(decoded_3, 3);
    encoder.append_uint(decoded_4, 4);
    expect(encoder.toUint8Array()).toEqual(encoded);

    var decoder = new Decoder(encoded);
    expect(decoder.read_uint(1)).toEqual(decoded_1);
    expect(decoder.read_uint(2)).toEqual(decoded_2);
    expect(decoder.read_uint(3)).toEqual(decoded_3);
    expect(decoder.read_uint(4)).toEqual(decoded_4);
});

test('bool', () => {
    var decoded_1 = true;
    var decoded_2 = false;
    var encoded = new Uint8Array([255, 0]);

    var encoder = new Encoder();
    encoder.append_bool(decoded_1);
    encoder.append_bool(decoded_2);
    expect(encoder.toUint8Array()).toEqual(encoded);

    var decoder = new Decoder(encoded);
    expect(decoder.read_bool()).toEqual(decoded_1);
    expect(decoder.read_bool()).toEqual(decoded_2);
});

test('length_determinant', () => {
    var decoded_1 = 0;
    var decoded_2 = 127;
    var decoded_3 = 128;
    var decoded_4 = 255;
    var decoded_5 = 256;
    var decoded_6 = 65535;
    var decoded_7 = 65536;
    var decoded_8 = 16777215;
    var decoded_9 = 16777216;
    var encoded = new Uint8Array([
        0,
        127,
        0x81, 128,
        0x81, 255,
        0x82, 1, 0,
        0x82, 255, 255,
        0x83, 1, 0, 0,
        0x83, 255, 255, 255,
        0x84, 1, 0, 0, 0
    ]);

    var encoder = new Encoder();
    encoder.append_length_determinant(decoded_1);
    encoder.append_length_determinant(decoded_2);
    encoder.append_length_determinant(decoded_3);
    encoder.append_length_determinant(decoded_4);
    encoder.append_length_determinant(decoded_5);
    encoder.append_length_determinant(decoded_6);
    encoder.append_length_determinant(decoded_7);
    encoder.append_length_determinant(decoded_8);
    encoder.append_length_determinant(decoded_9);
    expect(encoder.toUint8Array()).toEqual(
        new Uint8Array([
            0,
            127,
            0x81, 128,
            0x81, 255,
            0x82, 1, 0,
            0x82, 255, 255,
            0x83, 1, 0, 0,
            0x83, 255, 255, 255,
            0x84, 1, 0, 0, 0
        ]));

    var decoder = new Decoder(encoded);
    expect(decoder.read_length_determinant()).toEqual(decoded_1);
    expect(decoder.read_length_determinant()).toEqual(decoded_2);
    expect(decoder.read_length_determinant()).toEqual(decoded_3);
    expect(decoder.read_length_determinant()).toEqual(decoded_4);
    expect(decoder.read_length_determinant()).toEqual(decoded_5);
    expect(decoder.read_length_determinant()).toEqual(decoded_6);
    expect(decoder.read_length_determinant()).toEqual(decoded_7);
    expect(decoder.read_length_determinant()).toEqual(decoded_8);
    expect(decoder.read_length_determinant()).toEqual(decoded_9);
});

test('read_tag', () => {
    var decoded_1 = 0;
    var decoded_2 = 0x3e;
    var decoded_3 = 0x3f00;
    var decoded_4 = 0x40;
    var decoded_5 = 0xffff7f;
    var decoded_6 = 0xff80807f;
    var encoded = new Uint8Array([
        0,
        0x3e,
        0x3f,
        0x00,
        0x40,
        0xff,
        0xff,
        0x7f,
        0xff,
        0x80,
        0x80,
        0x7f
    ]);

    var decoder = new Decoder(encoded);
    expect(decoder.read_tag()).toEqual(decoded_1);
    expect(decoder.read_tag()).toEqual(decoded_2);
    expect(decoder.read_tag()).toEqual(decoded_3);
    expect(decoder.read_tag()).toEqual(decoded_4);
    expect(decoder.read_tag()).toEqual(decoded_5);
    expect(decoder.read_tag()).toEqual(decoded_6);
});

test('c_source_a', () => {
    var message = new CSourceA();
    var decoded = new CSourceA();
    decoded.a = -1;
    decoded.b = -2;
    decoded.c = -3;
    decoded.e = 1;
    decoded.f = 2;
    decoded.g = 3;
    decoded.i = true;
    decoded.j = new Uint8Array([5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5]);
    var encoded = new Uint8Array([
        0xff,
        0xff, 0xfe,
        0xff, 0xff, 0xff, 0xfd,
        1,
        0, 2,
        0, 0, 0, 3,
        0xff,
        5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5
    ]);

    expect(decoded.toUint8Array()).toEqual(encoded);
    message.fromUint8Array(encoded);
    expect(message.a).toEqual(decoded.a);
    expect(message.b).toEqual(decoded.b);
    expect(message.c).toEqual(decoded.c);
    expect(message.e).toEqual(decoded.e);
    expect(message.f).toEqual(decoded.f);
    expect(message.g).toEqual(decoded.g);
    expect(message.i).toEqual(decoded.i);
    expect(message.j).toEqual(decoded.j);
});

test('c_source_a_decode_error_out_of_data', () => {
    var message = new CSourceA();
    var encoded = new Uint8Array([
        0xff,
        0xff, 0xfe,
        0xff, 0xff, 0xff, 0xfd,
        1,
        0, 2,
        0, 0, 0, 3,
        0xff,
        5, 5, 5, 5, 5, 5, 5, 5, 5, 5
    ]);

    expect(() => message.fromUint8Array(encoded)).toThrow("Out of data.");
});

test('c_source_b_choice_a', () => {
    var message = new CSourceB();
    var decoded = new CSourceB();
    decoded.choice = CSourceB.CHOICE_A;
    decoded.value.a = -10;
    var encoded = new Uint8Array([0x80, 0xf6]);

    expect(decoded.toUint8Array()).toEqual(encoded);
    message.fromUint8Array(encoded);
    expect(message.choice).toEqual(decoded.choice);
    expect(message.value.a).toEqual(decoded.value.a);
});
