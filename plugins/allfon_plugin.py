# -*- coding: utf-8 -*-
'''
Allfon.tv Playlist Downloader Plugin
http://ip:port/allfon
'''

__author__ = 'miltador, Dorik1972'

import logging
import requests, time, zlib
from urllib3.packages.six.moves.urllib.parse import parse_qs
from PluginInterface import AceProxyPlugin
from PlaylistGenerator import PlaylistGenerator
import config.allfon as config

class Allfon(AceProxyPlugin):

    # ttvplaylist handler is obsolete
    handlers = ('allfon',)

    logger = logging.getLogger('plugin_allfon')
    playlist = None
    playlisttime = None

    def __init__(self, AceConfig, AceProxy): pass

    def downloadPlaylist(self):
        headers = {'User-Agent': 'Magic Browser'}
        try:
            Allfon.playlist = requests.get(config.url, headers=headers, proxies=config.proxies, stream=False, timeout=30)
            if Allfon.playlist.encoding is None: Allfon.playlist.encoding = 'utf-8'
            Allfon.logger.debug('AllFon playlist %s downloaded !' % config.url)
            Allfon.playlisttime = int(time.time())
        except requests.exceptions.RequestException:
            Allfon.logger.error("Can't download AllFonTV playlist!")
            return False
        else: return True

    def handle(self, connection, headers_only=False):

        hostport = connection.headers['Host']
        if headers_only:
            connection.send_response(200)
            connection.send_header('Content-Type', 'audio/mpegurl; charset=utf-8')
            connection.send_header('Connection', 'close')
            connection.end_headers()
            return

        # 15 minutes cache
        if not Allfon.playlist or (int(time.time()) - Allfon.playlisttime > 15 * 60):
            if not self.downloadPlaylist(): connection.dieWithError(); return

        playlistgen = PlaylistGenerator(m3uchanneltemplate=config.m3uchanneltemplate)

        Allfon.logger.debug('Generating requested m3u playlist')

        pattern = requests.auth.re.compile(r',(?P<name>.+)[\r\n].+[\r\n].+[\r\n](?P<url>[^\r\n]+)?')
        for match in pattern.finditer(Allfon.playlist.text, requests.auth.re.MULTILINE): playlistgen.addItem(match.groupdict())

        Allfon.logger.debug('Exporting m3u playlist')
        params = parse_qs(connection.query)
        add_ts = True if connection.path.endswith('/ts') else False

        exported = playlistgen.exportm3u(hostport, header=config.m3uheadertemplate, add_ts=add_ts, fmt=params.get('fmt', [''])[0])

        connection.send_response(200)
        connection.send_header('Content-Type', 'audio/mpegurl; charset=utf-8')
        connection.send_header('Access-Control-Allow-Origin', '*')
        try:
           h = connection.headers.get('Accept-Encoding').split(',')[0]
           compress_method = { 'zlib': zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS),
                               'deflate': zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS),
                               'gzip': zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16) }
           exported = compress_method[h].compress(exported) + compress_method[h].flush()
           connection.send_header('Content-Encoding', h)
        except: pass
        connection.send_header('Content-Length', len(exported))
        connection.send_header('Connection', 'close')
        connection.end_headers()

        connection.wfile.write(exported)
