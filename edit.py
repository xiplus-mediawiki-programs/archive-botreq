# -*- coding: utf-8 -*-
import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime

os.environ['PYWIKIBOT_DIR'] = os.path.dirname(os.path.realpath(__file__))
import pywikibot

from config import config_page_name  # pylint: disable=E0611,W0614

os.environ['TZ'] = 'UTC'


class ArchiveBotreq:
    RANDOM_SEP = str(uuid.uuid1())

    def __init__(self, config_page_name, args):
        self.args = args

        self.site = pywikibot.Site()
        self.site.login()

        self.logger = logging.getLogger('archive_botreq')
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        self.logger.addHandler(stdout_handler)

        config_page = pywikibot.Page(self.site, config_page_name)
        self.cfg = json.loads(config_page.text)
        self.logger.debug('config: %s', json.dumps(self.cfg, indent=4, ensure_ascii=False))

    def find_last_time(self, text):
        lasttime = datetime(1, 1, 1)
        for m in re.findall(r'(\d{4})年(\d{1,2})月(\d{1,2})日 \(.\) (\d{2}):(\d{2}) \(UTC\)', text):
            d = datetime(int(m[0]), int(m[1]), int(m[2]), int(m[3]), int(m[4]))
            lasttime = max(lasttime, d)
        return lasttime

    def check_archive(self, text):
        last_time = self.find_last_time(text)
        if last_time == datetime(1, 1, 1):
            return False
        if re.search(r'{{[\s_]*(不存檔|不存档|请勿存档|請勿存檔|Do[ _]+not[ _]+archive|DNA)[\s_]*(\||}})', text, flags=re.I):
            return False
        if time.time() - last_time.timestamp() > 86400 * 183:
            return True
        if time.time() - last_time.timestamp() > 86400 * 14 and re.search(r'{{[\s_]*(完成|Done|Finish)[\s_]*(\||}})', text, flags=re.I):
            return True
        return False

    def main(self):
        self.logger.info('start')
        if not self.cfg['enable']:
            self.logger.warning('disabled')
            return

        mainPage = pywikibot.Page(self.site, self.cfg['main_page_name'])
        text = mainPage.text

        text = re.sub(r'^(==[^=]+==)$', self.RANDOM_SEP + r'\1', text, flags=re.M)
        text = text.split(self.RANDOM_SEP)
        self.logger.debug('found %d sections', len(text) - 1)

        mainPageText = text[0].strip()

        today = datetime.today()
        archivePagename = self.cfg['archive_page_name'].format(today.year, today.month)
        self.logger.debug('archive page: %s', archivePagename)
        archivePage = pywikibot.Page(self.site, archivePagename)
        archiveText = archivePage.text
        if not archiveText:
            archiveText = '{{Talk archive|' + self.cfg['main_page_name'] + '}}'

        archiveCnt = 0
        for section in text[1:]:
            section = section.strip()
            title = section.split('\n')[0]
            self.logger.debug('run %s', title)

            to_archive = self.check_archive(section)
            if to_archive:
                self.logger.info('archive %s', title)
                archiveText += '\n\n' + section
                archiveCnt += 1
            else:
                mainPageText += '\n\n' + section

        if archiveCnt == 0:
            self.logger.info('nothing changed')
            return

        # Save main page
        summary = self.cfg['main_page_summary'].format(archiveCnt)
        if self.args.confirm or self.args.loglevel <= logging.DEBUG:
            pywikibot.showDiff(mainPage.text, mainPageText)
            self.logger.info('main summary: %s', summary)

        save = True
        if self.args.confirm:
            save = pywikibot.input_yn('Save changes for main page?', 'Y')
        if save:
            self.logger.debug('save changes')
            mainPage.text = mainPageText
            mainPage.save(summary=summary, minor=False)
        else:
            self.logger.debug('skip save')

        # Save archive page
        summary = self.cfg['archive_page_summary'].format(archiveCnt)
        if self.args.confirm or self.args.loglevel <= logging.DEBUG:
            pywikibot.showDiff(archivePage.text, archiveText)
            self.logger.info('archive summary: %s', summary)

        save = True
        if self.args.confirm:
            save = pywikibot.input_yn('Save changes for archive page?', 'Y')
        if save:
            self.logger.debug('save changes')
            archivePage.text = archiveText
            archivePage.save(summary=summary, minor=False)
        else:
            self.logger.debug('skip save')

        self.logger.info('done')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--confirm', action='store_true')
    parser.add_argument('-d', '--debug', action='store_const', dest='loglevel', const=logging.DEBUG, default=logging.INFO)
    args = parser.parse_args()

    mark_itntalk = ArchiveBotreq(config_page_name, args)
    mark_itntalk.logger.setLevel(args.loglevel)
    mark_itntalk.logger.debug('args: %s', args)
    mark_itntalk.main()
