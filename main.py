#!/usr/bin/env python3

import os, sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
import requests
from collections import namedtuple


TEMPLATE_SOUP = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title></title>
    <style>
        img { max-width: 96vw; margin: 10px 2vw; }
        .nav { display: flex; justify-content: space-between; font-size: 1rem;}
        .nav > a, .nav > span { display: inline-block; }
        .nav > a.disabled { cursor: not-allowed; pointer-events: none; text-decoration: none; color: #888888; }
    </style>
</head>
<body>
</body>
</html>
'''

NAV_TEMPLATE_SOUP = '''
<hr>
<div class="nav">
    <a href="page-000.html">{ #1 } &lt;&lt;</a>
    <a href="page-000.html">Prev</a>
    <span>{ #1 }</span>
    <a href="page-000.html">Next</a>
    <a href="page-000.html">To End</a>
</div>
<hr>
'''

def build_nav(current, max_page, linkf, divider='bottom'):
    s = BeautifulSoup(NAV_TEMPLATE_SOUP, features='lxml')

    current_span = s.select('div > span')[0]
    current_span.string = '{{ #{} }}'.format(current+1)

    first_a = s.select('div > a:nth-of-type(1)')[0]
    first_a['href'] = linkf(0)

    last_a = s.select('div > a:nth-of-type(4)')[0]
    last_a['href'] = linkf(max_page)
    last_a.string = '>> {{ #{} }}'.format(max_page+1)

    next_a = s.select('div > a:nth-of-type(3)')[0]
    if current+1 == max_page:
        next_a['class'] = last_a['class'] = 'disabled'
    else:
        next_a['href'] = linkf(current+1)
    
    prev_a = s.select('div > a:nth-of-type(2)')[0]
    if current == 0:
        prev_a['class'] = first_a['class'] = 'disabled'
    else:
        prev_a['href'] = linkf(current-1)

    # if divider == 'bottom':
    #     s.append(s.new_tag('hr'))
    # elif divider == 'top':
    #     s.insert(0, s.new_tag('hr'))

    return s


HOST = 'http://loveread.ec'
BOOK_URL = HOST + '/read_book.php'

# todo: generate index.html
BOOK_INFO_URL = '/view_global.php'
BOOK_CONTENTS_URL '/contents.php'


def download_image(url, path):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with path.open(mode='wb') as f:
            for chunk in r:
                f.write(chunk)


def filename_for_page(i):
    return '{:03}.html'.format(i)


def scrape(book_id: int, target_directory: Path):
    images_directory = target_directory / 'imgs'
    images_directory.mkdir(exist_ok=True)

    pages_directory = target_directory / 'pages'
    pages_directory.mkdir(exist_ok=True)

    start_page = 1
    max_page = 1
    
    request_params = dict(id=book_id)

    i = 0
    while True:
        request_params['p'] = i+1
        r = requests.get(BOOK_URL, params=request_params, allow_redirects=False)

        # max page num exceeded
        if r.status_code >= 300:
            break

        soap = BeautifulSoup(r.content, features="lxml")

        content = soap.select('td[class=tb_read_book]')[0]
        if i == 0:
            navigation = content.select('div + div + div + div')[0]
            for ch in navigation.children:
                try:
                    max_page = max(max_page, int(ch.string))-1
                except ValueError:
                    pass

        content = content.select('div + div + div > div')[0]

        del content['style'], content['class']

        # remove navigation forms
        top_nav = next(i for i in content.contents if not isinstance(i, NavigableString))
        bottom_nav = next(i for i in reversed(content.contents) if not isinstance(i, NavigableString))
        top_nav.decompose()
        bottom_nav.decompose()


        for a in content.find_all('a'):
            if 'href' in a:
                a['href'] = HOST + '/' + a['href']

        for img in content.find_all('img'):
            # img['src'] = HOST + '/' + img['src'];
            img_url = HOST + '/' + img['src']
            img_local_path = images_directory / Path(img['src']).name
            if not img_local_path.exists():
                download_image(img_url, img_local_path)
            del img['style']
            img['src'] = '../{}'.format(img_local_path.relative_to(target_directory))

        page = BeautifulSoup(TEMPLATE_SOUP, features='lxml')
        page.title.string = '{} - page #{}'.format(target_directory.name, i+1)

        linkf = lambda i: '../{}'.format((pages_directory / filename_for_page(i)).relative_to(target_directory))

        page.body.append(build_nav(i, max_page, linkf, divider='bottom'))
        page.body.append(content)
        page.body.append(build_nav(i, max_page, linkf, divider='top'))

        page_path = pages_directory / filename_for_page(i)

        with page_path.open(mode='w') as f:
            f.write(str(page))

        if i == 0:
            index_path = target_directory / 'index.html'
            if index_path.is_symlink():
                index_path.unlink()
            # index_path.symlink_to(page_path.relative_to(index_path.parent))
            # print('index:', index_path)

        print('page #{}:'.format(i), page_path)

        i += 1  


def main():

    try:
        book_id = int(sys.argv[1])
        target_directory = Path(sys.argv[2])
    except (ValueError, TypeError, IndexError):
        exit('invalid arguments: %r' % sys.argv[1:])

    target_directory.mkdir(exist_ok=True)

    scrape(book_id, target_directory)


if __name__ == '__main__':
    main()
