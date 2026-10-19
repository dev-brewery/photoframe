#!/usr/bin/env python3
"""
Validate a photoframe display driver package.

Usage:
    python3 validate-driver.py driver.zip

The INSTALL file format allows duplicate keys and bare values (non-standard INI),
so this validator uses simple text parsing rather than configparser.
"""

import sys
import zipfile
import re


def parse_install_file(content):
    """Parse INSTALL file, returning sections dict."""
    sections = {}
    current_section = None

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue

        section_match = re.match(r'^\[(\w+)\]$', line)
        if section_match:
            current_section = section_match.group(1).lower()
            sections[current_section] = []
        elif current_section is not None:
            sections[current_section].append(line)

    return sections


def validate_driver(zippath):
    errors = []
    warnings = []

    try:
        with zipfile.ZipFile(zippath) as z:
            names = z.namelist()

            install_files = [n for n in names if n.endswith('INSTALL')]
            if not install_files:
                errors.append("No INSTALL file found in archive")
                return errors, warnings

            if len(install_files) > 1:
                warnings.append(f"Multiple INSTALL files found: {install_files}")

            install_path = install_files[0]
            install_dir = '/'.join(install_path.split('/')[:-1])
            if install_dir:
                install_dir += '/'

            try:
                content = z.read(install_path).decode('utf-8')
            except Exception as e:
                errors.append(f"Cannot read INSTALL file: {e}")
                return errors, warnings

            sections = parse_install_file(content)

            if 'install' not in sections:
                errors.append("Missing [install] section in INSTALL file")

            if 'config' not in sections:
                errors.append("Missing [config] section in INSTALL file")

            if 'install' in sections:
                for line in sections['install']:
                    if '=' in line:
                        src_file = line.split('=')[0].strip()
                        full_path = install_dir + src_file
                        if full_path not in names and src_file not in names:
                            errors.append(f"File referenced in [install] not found: {src_file}")

            if 'config' in sections and not sections['config']:
                warnings.append("[config] section is empty")

            for name in names:
                if name.startswith('/') or '..' in name:
                    errors.append(f"Suspicious path in archive: {name}")

    except zipfile.BadZipFile:
        errors.append("Not a valid ZIP file")
    except Exception as e:
        errors.append(f"Error reading archive: {e}")

    return errors, warnings


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <driver.zip>")
        sys.exit(1)

    zippath = sys.argv[1]
    print(f"Validating: {zippath}")
    print()

    errors, warnings = validate_driver(zippath)

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")
        print()

    if errors:
        print("Errors:")
        for e in errors:
            print(f"  - {e}")
        print()
        print("FAILED: Driver package has errors")
        sys.exit(1)
    else:
        print("OK: Driver package is valid")
        sys.exit(0)


if __name__ == '__main__':
    main()
