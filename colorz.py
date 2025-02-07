#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A color scheme generator.

Takes an image (local or online) and grabs the most dominant colors
using kmeans.
Also creates bold colors by adding value to the dominant colors.

Finally, outputs the colors to stdout
(one normal and one bold per line, space delimited) and
generates an HTML preview of the color scheme.
"""

import os
import webbrowser
from sys import exit
from io import BytesIO
from tempfile import NamedTemporaryFile
from argparse import ArgumentParser
from PIL import Image
from numpy import array
from scipy.cluster.vq import kmeans
from colorsys import rgb_to_hsv, hsv_to_rgb

# Python3 compatibility
try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen

DEFAULT_NUM_COLORS = 6
DEFAULT_MINV = 170
DEFAULT_MAXV = 200
DEFAULT_BOLD_ADD = 50
DEFAULT_FONT_SIZE = 1
DEFAULT_BG_COLOR = '#272727'

THUMB_SIZE = (200, 200)
SCALE = 256.0


def down_scale(x):
    return x / SCALE


def up_scale(x):
    return int(x * SCALE)


def hexify(rgb):
    return '#%s' % ''.join('%02x' % p for p in rgb)


def get_colors(img):
    """
    Returns a list of all the image's colors.
    """
    w, h = img.size
    return [color[:3] for count, color in img.convert('RGB').getcolors(w * h)]


def clamp(color, min_v, max_v):
    """
    Clamps a color such that the value is between min_v and max_v.
    """
    h, s, v = rgb_to_hsv(*map(down_scale, color))
    min_v, max_v = map(down_scale, (min_v, max_v))
    v = min(max(min_v, v), max_v)
    return tuple(map(up_scale, hsv_to_rgb(h, s, v)))


def order_by_hue(colors):
    """
    Orders colors by hue.
    """
    hsvs = [rgb_to_hsv(*map(down_scale, color)) for color in colors]
    hsvs.sort(key=lambda t: t[0])
    return [tuple(map(up_scale, hsv_to_rgb(*hsv))) for hsv in hsvs]


def brighten(color, brightness):
    """
    Adds or subtracts value to a color.
    """
    h, s, v = rgb_to_hsv(*map(down_scale, color))
    return tuple(map(up_scale, hsv_to_rgb(h, s, v + down_scale(brightness))))


def colorz(fd, n=DEFAULT_NUM_COLORS, min_v=DEFAULT_MINV, max_v=DEFAULT_MAXV,
           bold_add=DEFAULT_BOLD_ADD, order_colors=True):
    """
    Get the n most dominant colors of an image.
    Clamps value to between min_v and max_v.

    Creates bold colors using bold_add.
    Total number of colors returned is 2*n, optionally ordered by hue.
    Returns as a list of pairs of RGB triples.

    For terminal colors, the hue order is:
    red, yellow, green, cyan, blue, magenta
    """
    img = Image.open(fd)
    if img.is_animated:
        img.seek(1)
    img.thumbnail(THUMB_SIZE)

    obs = get_colors(img)
    clamped = [clamp(color, min_v, max_v) for color in obs]
    clusters, _ = kmeans(array(clamped).astype(float), n)
    colors = order_by_hue(clusters) if order_colors else clusters
    return list(zip(colors, [brighten(c, bold_add) for c in colors]))


def html_preview(colors, font_size=DEFAULT_FONT_SIZE,
                 bg_color=DEFAULT_BG_COLOR, bg_img=None,
                 fd=None):
    """
    Creates an HTML preview of each color.

    Returns the Python file object for the HTML file.
    """

    fd = fd or NamedTemporaryFile(mode='wt', suffix='.html', delete=False)

    # Initial CSS styling is empty
    style = ""

    # Create the main body
    body = '\n'.join(["""
        <div class="color" style="color: {color}">
            <div>█ {color}</div>
            <div style="color: {color_bold}">
                <strong>█ {color_bold}</strong>
            </div>
        </div>
    """.format(color=hexify(c[0]), color_bold=hexify(c[1])) for c in colors])

    if bg_img:
        # Check if local or online image
        if os.path.isfile(bg_img):
            bg_img = os.path.abspath(bg_img)

        bg_url = "url('%s')" % (
            ('file://%s' % bg_img) if os.path.isfile(bg_img) else bg_img)

        # Add preview box and image to the body
        body = """
            <div id="preview-box" class="box-shadow">
                <img id="preview-image" class="box-shadow" src="{bg_img}" />
                {body}
            </div>
        """.format(**locals())

        # Add blurred background image styling
        style += """
            body:before {{
                content: '';
                position: fixed;
                z-index: -1;
                left: 0;
                right: 0;
                width: 100%;
                height: 100%;
                display: block;

                background-image: {bg_url};
                background-size: cover;
                background-repeat: no-repeat;
                background-position: center center;
                background-attachment: fixed;

                -webkit-filter: blur(2rem);
                -moz-filter: blur(2rem);
                -o-filter: blur(2rem);
                -ms-filter: blur(2rem);
                filter: blur(2rem)
            }}
        """.format(**locals())

    # CSS styling
    style += """
        body {{
            margin: 0;
            background: {bg_color};

            font-family: monospace;
            font-size: {font_size}rem;
            line-height: 1;
        }}

        #main-container {{
            padding: 1rem;
            text-align: center;
        }}

        #preview-box {{
            display: inline-block;
            margin: 3rem;
            padding: 1rem;
            background: {bg_color};
        }}

        #preview-image {{
            width: 100%;
        }}

        .color {{
            display: inline-block;
            margin: 1rem;
        }}

        .box-shadow {{
            -webkit-box-shadow: 0 0 1em 0 rgba(0, 0, 0, 0.75);
            -moz-box-shadow:    0 0 1em 0 rgba(0, 0, 0, 0.75);
            box-shadow:         0 0 1em 0 rgba(0, 0, 0, 0.75);
        }}
    """.format(**locals())

    # Write the file
    fd.write("""
        <!DOCTYPE html>
        <html>
            <head>
                <title>
                    Colorscheme Preview
                </title>
                <meta charset="utf-8">
                <style>
                    {style}
                </style>
            </head>
            <body>
                <div id="main-container">
                    {body}
                </div>
            </body>
        </html>
    """.format(**locals()))

    return fd


def parse_args():
    parser = ArgumentParser(description=__doc__)

    parser.add_argument('image',
                        help="""
                        the image file or url to generate from.
                        """,
                        type=str)

    parser.add_argument('-n',
                        help="""
                        number of colors to generate (excluding bold).
                        Default: %s
                        """ % DEFAULT_NUM_COLORS,
                        dest='num_colors',
                        type=int,
                        default=DEFAULT_NUM_COLORS)

    parser.add_argument('--minv',
                        help="""
                        minimum value for the colors.
                        Default: %s
                        """ % DEFAULT_MINV,
                        type=int,
                        default=DEFAULT_MINV)

    parser.add_argument('--maxv',
                        help="""
                        maximum value for the colors.
                        Default: %s
                        """ % DEFAULT_MAXV,
                        type=int,
                        default=DEFAULT_MAXV)

    parser.add_argument('--bold',
                        help="""
                        how much value to add for bold colors.
                        Default: %s
                        """ % DEFAULT_BOLD_ADD,
                        type=int,
                        default=DEFAULT_BOLD_ADD)

    parser.add_argument('--font-size',
                        help="""
                        what font size to use, in rem.
                        Default: %s
                        """ % DEFAULT_FONT_SIZE,
                        type=int,
                        default=DEFAULT_FONT_SIZE)

    parser.add_argument('--bg-color',
                        help="""
                        what background color to use, in hex format.
                        Default: %s
                        """ % DEFAULT_BG_COLOR,
                        type=str,
                        default=DEFAULT_BG_COLOR)

    parser.add_argument('--no-bg-img',
                        help="""
                        whether or not to use a background image in the
                        preview.
                        Default: background image on
                        """,
                        action='store_true',
                        default=False)

    parser.add_argument('--no-preview',
                        help="""
                        whether or not to generate and show the preview.
                        Default: preview on
                        """,
                        action='store_true',
                        default=False)

    return parser.parse_args()


def main():
    args = parse_args()

    # Open local file or online file
    try:
        img_fd = open(args.image, 'rb') if os.path.isfile(args.image) else \
            BytesIO(urlopen(args.image).read())
    except ValueError:
        print("%s was not a valid URL." % args.image)
        exit(1)

    colors = colorz(img_fd, args.num_colors, args.minv, args.maxv, args.bold)

    for pair in colors:
        print('%s %s' % tuple(map(hexify, pair)))

    if not args.no_preview:
        html_fd = html_preview(colors, args.font_size, args.bg_color,
                               args.image if not args.no_bg_img else None)

        # Suppress stdout from browser
        # http://stackoverflow.com/a/2323563
        os.close(1)
        os.close(2)
        webbrowser.open('file://%s' % html_fd.name)


if __name__ == '__main__':
    main()
