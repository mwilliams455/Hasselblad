#!/usr/bin/env python3
"""Parse local FlatBuffers-style IQ JSON as inert data and report structure.

Supports comments, unquoted identifiers, enum literals, hexadecimal integers,
and trailing commas. This does not execute or convert any firmware code.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'firmware/extracted/system/etc/iq/hb722_config.json'
SOURCE_SHA256 = '2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286'
TOKEN = re.compile(r'(?P<space>\s+)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|'
                   r'(?P<string>"(?:\\.|[^"\\])*")|'
                   r'(?P<number>[+-]?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?))|'
                   r'(?P<identifier>[A-Za-z_][A-Za-z0-9_]*)|(?P<punctuation>[{}\[\]:,])')


class Parser:
    def __init__(self, source):
        self.source, self.offset, self.next = source, 0, None
        self.advance()

    def advance(self):
        while self.offset < len(self.source):
            match = TOKEN.match(self.source, self.offset)
            if not match:
                raise ValueError(f'Unexpected token at offset {self.offset}: {self.source[self.offset:self.offset+80]!r}')
            self.offset = match.end()
            if match.lastgroup in ('space', 'comment'):
                continue
            self.next = (match.lastgroup, match.group())
            return
        self.next = None

    def consume(self, text):
        if self.next is None or self.next[1] != text:
            raise ValueError(f'Expected {text!r}, found {self.next!r} at {self.offset}')
        self.advance()

    def value(self, depth=0):
        if depth > 32 or self.next is None:
            raise ValueError('Unexpected depth or end of data')
        kind, token = self.next
        if token == '{':
            self.advance()
            result = {}
            while self.next and self.next[1] != '}':
                key_kind, key_token = self.next
                if key_kind not in ('identifier', 'string'):
                    raise ValueError('Object key is not an identifier/string')
                key = json.loads(key_token) if key_kind == 'string' else key_token
                self.advance()
                self.consume(':')
                if key in result:
                    raise ValueError(f'Duplicate key: {key}')
                result[key] = self.value(depth + 1)
                if self.next and self.next[1] == ',':
                    self.advance()
                elif self.next is None or self.next[1] != '}':
                    raise ValueError('Object requires comma or closing brace')
            self.consume('}')
            return result
        if token == '[':
            self.advance()
            result = []
            while self.next and self.next[1] != ']':
                result.append(self.value(depth + 1))
                if self.next and self.next[1] == ',':
                    self.advance()
                elif self.next is None or self.next[1] != ']':
                    raise ValueError('Array requires comma or closing bracket')
            self.consume(']')
            return result
        self.advance()
        if kind == 'number':
            if 'x' in token.lower():
                return int(token, 16)
            return float(token) if '.' in token or 'e' in token.lower() else int(token)
        if kind == 'string':
            return json.loads(token)
        if kind == 'identifier':
            return {'true': True, 'false': False, 'null': None}.get(token, token)
        raise ValueError(f'Unexpected value token: {token}')


def read_config(source=SOURCE):
    payload = Path(source).read_bytes()
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError('IQ config does not match the audited X2D II 1.3.16.2 SHA256')
    parser = Parser(payload.decode('utf-8'))
    config = parser.value()
    if parser.next is not None:
        raise ValueError('Unexpected trailing data')
    return config


def shape(value):
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list) and len(value) > 20 and all(isinstance(x, (float, int)) for x in value):
        return {'length': len(value), 'first': value[:8], 'last': value[-8:],
                'min': min(value), 'max': max(value),
                'values_json_sha256': hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()}
    if isinstance(value, list):
        return [shape(item) for item in value]
    return value


def main():
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument('--source', type=Path, default=SOURCE)
    arguments.add_argument('--output', type=Path, default=Path(__file__).parent / 'iq_config_summary.json')
    args = arguments.parse_args()
    config = read_config(args.source)
    with args.source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    result = {'source': str(args.source), 'sha256': digest, 'root_keys': list(config),
              'parser_provenance': 'Original local research tool; inert tokenization and recursive descent, no eval or vendor parser execution',
              'parser_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'camera_axes': {key: config['camera'].get(key) for key in
                              ('color_temp', 'cc_color_temp', 'color_gamut', 'gain', 'local_lut3d_num')},
              'topology': shape(config.get('topology')), 'iq_table_keys': list(config.get('iq_table', {})),
              'selected_modules': []}
    selected = {'main_hncs', 'main_ccm', 'main_3dlut', 'main_gamma_common', 'main_gamma_normal',
                'main_gamma_lowlight', 'post_hdr', 'post_scap3', 'main_autoknee'}

    def walk(value, path):
        if isinstance(value, dict):
            mode = {key: val for key, val in value.items() if 'mode' in key and isinstance(val, (str, int))}
            for key, item in value.items():
                if key in selected:
                    result['selected_modules'].append({'path': path + '/' + key, 'parent_mode': mode, 'value': shape(item)})
                elif isinstance(item, (dict, list)):
                    walk(item, path + '/' + key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, (dict, list)):
                    walk(item, path + '/' + str(index))

    walk(config.get('iq_table', {}), 'iq_table')
    target = args.output
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in ('selected_modules', 'topology')}))
    print('SELECTED_MODULES', [(item['path'], item['parent_mode']) for item in result['selected_modules']])
    print('REPORT', target)


if __name__ == '__main__':
    main()
