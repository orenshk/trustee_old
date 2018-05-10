#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import importlib

def main():
    parser = argparse.ArgumentParser(prog='trustee')
    subparsers = parser.add_subparsers(title='sources', dest='source')
    subparsers.required = True
    subparsers.add_parser('ec2')

    args, source_args = parser.parse_known_args()

    source = importlib.import_module(f'trustee.{args.source}')
    source.main(source_args)

if __name__ == '__main__':
    main()
