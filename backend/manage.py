"""Offline account provisioning. Passwords are read from a terminal, never CLI arguments."""
import argparse
import getpass

from .db import connect, initialize
from .security import hash_password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    municipality = sub.add_parser('create-municipality')
    municipality.add_argument('--name', required=True)
    account = sub.add_parser('create-user')
    account.add_argument('--name', required=True)
    account.add_argument('--email', required=True)
    account.add_argument('--role', required=True, choices=['admin', 'clerk', 'reviewer', 'inspector', 'applicant'])
    account.add_argument('--municipality-id', required=True, type=int)
    args = parser.parse_args()
    initialize()
    with connect() as db:
        if args.command == 'create-municipality':
            if not 2 <= len(args.name.strip()) <= 120:
                parser.error('Municipality name must be 2–120 characters.')
            cursor = db.execute('INSERT INTO municipalities(name) VALUES(?)', (args.name.strip(),))
            print(f'Municipality created: id={cursor.lastrowid}')
        else:
            if '@' not in args.email or not args.name.strip():
                parser.error('Provide a valid name and email.')
            password = getpass.getpass('Password (at least 12 characters): ')
            if len(password) < 12 or password != getpass.getpass('Confirm password: '):
                parser.error('Passwords must match and contain at least 12 characters.')
            if not db.execute('SELECT 1 FROM municipalities WHERE id=?', (args.municipality_id,)).fetchone():
                parser.error('Create the municipality first.')
            cursor = db.execute('INSERT INTO users(name,email,password_hash,role,municipality_id) VALUES(?,?,?,?,?)',
                                (args.name.strip(), args.email.strip().lower(), hash_password(password), args.role, args.municipality_id))
            if args.role == 'applicant':
                db.execute('INSERT INTO applicants(municipality_id,name,email,phone) VALUES(?,?,?,?)',
                           (args.municipality_id, args.name.strip(), args.email.strip().lower(), ''))
            print(f'User created: id={cursor.lastrowid}')


if __name__ == '__main__':
    main()
