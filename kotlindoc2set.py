import shutil, os
import sqlite3
from subprocess import call
from bs4 import BeautifulSoup
import re


URL = 'https://kotlinlang.org/api/latest/jvm/stdlib/index.html'
DOCUMENT_PATH = "kotlin.docset/Contents/Resources/Documents/"

def setup_directories(local_path: str):
    if os.path.exists(local_path):
        shutil.rmtree(local_path, ignore_errors=True)
    os.makedirs(local_path)

def mirror_website(url: str, local_path: str):
    call([
        'wget',
        '--mirror',
        '--convert-links',
        '--adjust-extension',
        '--page-requisites',
        '--no-parent',
        '--no-host-directories',
        '--directory-prefix', local_path,
        '--quiet',
        '--show-progress',
        url
    ])

def insert_into_index(cursor, name: str, doc_type: str, path: str):
    cursor.execute('INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES (?, ?, ?)', (name, doc_type, path))

def create_sqlite_index(cursor):
    try:
        cursor.execute("DROP TABLE searchIndex;")
    except:
        pass
    finally:
        cursor.execute('CREATE TABLE searchIndex(id INTEGER PRIMARY KEY, name TEXT, type TEXT, path TEXT);')
        cursor.execute('CREATE UNIQUE INDEX anchor ON searchIndex (name, type, path);')

def parse_code_type(code: str) -> str:
    tokens = list(filter(
        lambda token: token not in [
            'public',
            'private',
            'protected',
            'open',
            'const',
            'abstract',
            'suspend',
            'operator'
        ],
        code.split()
    ))
    if 'class' in tokens or 'typealias' in tokens:
        return 'Class'
    elif 'interface' in tokens:
        return 'Interface'
    elif 'fun' in tokens:
        return 'Function'
    elif 'val' in tokens or 'var' in tokens:
        return 'Property'
    elif 'object' in tokens:
        return 'Object'
    elif '<init>' in tokens or '<init>' in tokens[0]:
        return 'Constructor'
    elif re.match(r"[a-zA-Z0-9]*\(.*\)", code) or re.match(r"[a-zA-Z0-9]*\(.*\)", tokens[0]):
        return 'Constructor'
    elif re.match(r"[A-Z0-9\_]+", code):
        return 'Enum'

def parse_file(cursor: sqlite3.Cursor, file_path: str):
    with open(file_path) as page:
        soup = BeautifulSoup(page.read(), features='html.parser')
        for node in soup.find_all('div', attrs={'class': ['node-page-main', 'overload-group']}):

            signature = node.find('div', attrs={'class': 'signature'})
            if signature:
                code_type = parse_code_type(signature.text.strip())
                name_dom = soup.find('div', attrs={'class': 'api-docs-breadcrumbs'})
                name = '.'.join(map(lambda string: string.strip(), name_dom.text.split('/')[2::]))
                path = file_path.replace('kotlin.docset/Contents/Resources/Documents/', '')
                if code_type is not None and name:
                    insert_into_index(cursor, name, code_type, path)
                    print('%s -> %s -> %s' % (name, code_type, path))


def parse(cursor: sqlite3.Cursor, root_dir: str):
    for dirpath, _, files in os.walk(root_dir):
        for page in files:
            if page.endswith('.html'):
                parse_file(cursor, os.path.join(dirpath, page))

if __name__ == '__main__':
    setup_directories(DOCUMENT_PATH)
    mirror_website(URL, DOCUMENT_PATH)

    connection = sqlite3.connect('kotlin.docset/Contents/Resources/docSet.dsidx')
    cursor = connection.cursor()

    create_sqlite_index(cursor)
    parse(cursor, DOCUMENT_PATH)

    connection.commit()
    connection.close()
