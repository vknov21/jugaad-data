from bs4 import BeautifulSoup
import requests
from PyQt5 import QtWidgets, QtTest, QtCore
from datetime import datetime, timedelta
import sys
from MyMainWindow import MyMainWindow, BaseWorkerThread
import logging


def sports_keeda_webscraping(url, format, label):
    def screen_first_match(div, team_name_elements):
        team_score = team_group_div.find_all('span', class_='keeda_widget_score cricket')
        scorecard = ''
        for i in range(len(team_name_elements)):
            scorecard = scorecard + '\n' + team_name_elements[i].text + ": " + team_score[i].text
        return scorecard

    def create_matches_card(div, idx, team_name_elements):
        team_matches = set_text_colour(' vs '.join([element.text for element in team_name_elements]))
        href = div.find('a', class_="keeda_cricket_match_link").get('href').split('/')[-1] + "/ajax"
        return team_matches, href

    def set_text_colour(text, colour='blue'):
        return text
        return f'<font color="{colour}">{text}</font>'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://www.google.com/',
    }

    if format in [0, 1]:
        response = requests.get(url, headers=headers)
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the HTML content of the webpage
            soup = BeautifulSoup(response.text, 'html.parser')
        else:
            print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
            exit()

        target_div = soup.find('div', class_='keeda_widget_match_listing')
        # Find a div with a specific class inside the target_div
        inner_divs = target_div.find_all('div', class_='keeda_cricket_single_match')

        total_text_list = []
        href_list = []
        idx = 0

        for div in inner_divs:
            team_group_div = div.find('div', class_='keeda_widget_team_group')
            state = 'pre' if div.find('div', class_='keeda_cricket_match_list pre') else 'live' if div.find('div', class_='keeda_cricket_match_list live') else 'post'
            if team_group_div is None:
                continue
            idx += 1
            cric_match_list = div.find('div', class_='keeda_cricket_match_list ' + state)
            cric_info = cric_match_list.get('data-match-description')
            cric_time = cric_match_list.get('data-match-time')
            if cric_time:
                cric_time = ' | ' + str((datetime.strptime(cric_time, '%Y-%m-%dT%H:%M:%S%z') + timedelta(seconds=19800)).strftime('%a, %d %h %I:%M %p'))
            else:
                cric_time = ''
            div.find('div', class_='keeda_cricket_single_match')
            cur_status = div.find('div', 'keeda_widget_result_info ' + state).text
            cur_status = ' • '.join(cur_status.strip().split('\n'))
            team_name_elements = team_group_div.find_all('span', class_='keeda_widget_team_name cricket')
            if format == 0:
                scorecard = screen_first_match(div, team_name_elements)
                total_text = f"{cric_info}{cric_time}\n{scorecard.strip()}\n{cur_status}"
            else:
                total_text, href = create_matches_card(div, idx, team_name_elements)
                href_list.append(href)
            total_text_list.append(total_text)
        if format != 0:
            label.set_link(dict(enumerate(href_list, start=1)))
        return total_text_list

    if format == 2:
        fetch_json = requests.get(url, headers=headers).json()
        return fetch_json


class WorkerThread(BaseWorkerThread):
    def __init__(self, window):
        super().__init__(window)
        self.initial_base_url = 'https://www.sportskeeda.com/'
        self.initial_sub_url = ''
        self.base_url = 'https://www.sportskeeda.com/'
        self.sub_url = ''
        self.format = 1
        self.initiated = False
        self.wait_timer = 700
        self.initiating = False

    def fetch_from_link(self, line, source_obj):
        # sports_keeda_webscraping(self.base_url + self.sub_url, 1, self.window.label)
        try:
            stmt, self.sub_url = list(source_obj.get_link(line).items())[0]
        except IndexError:
            pass
        else:
            split_text = self.window.label.text().replace('🗘 ', '').split('\n')
            split_text[line - 1] = '🗘 ' + split_text[line - 1]
            self.setLabelTextandAdjust('\n'.join(split_text), keep_aspect=self.initiated)
            if self.initiated:
                self.wait_timer = 50
                self.format = 1
                self.base_url = self.initial_base_url
                self.sub_url = self.initial_sub_url
                self.trigger_per_format(no_wait=True)
                self.wait_timer = 700
                QtTest.QTest.qWait(700)
                self.initiated = False
            else:
                self.initiated = True
                self.wait_timer = 50
                self.format = 2
                self.base_url = "https://cmc2.sportskeeda.com/live-cricket-score/"
                self.window.label.line_link_dict = {}
                QtTest.QTest.qWait(700)
                self.wait_timer = 700
                self.initiated = False
                self.trigger_per_format(no_wait=True)

    def setLabelTextandAdjust(self, text, initial_format=None, initial_url=None, keep_aspect=False):
        # This is to avoid the case, where, the call was made for some format, which by the time it came in, was modified by some other parallel execution
        # In such cases, avoid updating the text, as it might be triggered by desperate multiple clicks or scrolls
        if initial_format and initial_format == self.format and \
                not (self.initiated or self.initiating):
            if initial_url and initial_url != self.base_url + self.sub_url:
                return
            QtCore.QMetaObject.invokeMethod(self.window.label, "setText", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(str, text))
        # Above case avoid the scene of already initiated overlay, but if that case is active, then change the text and perform the needed  operation
        elif self.initiated or self.initiating:
            QtCore.QMetaObject.invokeMethod(self.window.label, "setText", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(str, text))
        else:
            return
        QtTest.QTest.qWait(400)
        if keep_aspect is False:
            self.window.label.adjustSize()
        if self.window.label.line_link_dict:
            self.window.label.setStyleSheet("color: blue;")
        else:
            self.window.label.setStyleSheet("color: black;")
        self.resizeMainWindow(self.window.label.size().width(), self.window.label.size().height())

    def loader(self, text, format, url, no_wait=False):
        for i in range(9):
            if self.initiating:
                return
            self.setLabelTextandAdjust(text, initial_format=format, initial_url=url)
            if no_wait or self.initiating:
                return
            QtTest.QTest.qWait(self.wait_timer)
            if '•' in text and self.initiating is False:
                self.setLabelTextandAdjust(text.replace('•', ' '), initial_format=format, initial_url=url)
            if i == 7:
                break
            if self.initiating:
                return
            QtTest.QTest.qWait(self.wait_timer)
        if self.initiating is False:
            self.setLabelTextandAdjust(text.replace('•', '🗘'), initial_format=format, initial_url=url)

    def go_back(self):
        self.wait_timer = 50
        self.initiating = True
        # Wait 200 milisecond to avoid conflict with already executing run()
        QtTest.QTest.qWait(200)
        self.setLabelTextandAdjust("Go Back!", keep_aspect=True)
        self.initiated = True
        self.initiating = False
        self.wait_timer = 700
        self.window.label.set_link({1: self.initial_base_url})

    def is_initiated(self):
        return self.initiated

    def restore_layout(self):
        self.window.label.line_link_dict = {}
        self.trigger_per_format(no_wait=True)
        self.initiated = False

    def trigger_per_format(self, no_wait=False):
        url = self.base_url + self.sub_url
        text_data = sports_keeda_webscraping(url, self.format, self.window.label)

        if self.format == 0:
            if self.initiated is True and no_wait is False:
                return
            text = '\n'.join(text_data)
            self.window.label.setStyleSheet("color: black;")
            self.loader(text, format=0, no_wait=no_wait)
        elif self.format == 1:
            for _ in range(30):
                if _ == 29:
                    return
                # For waiting 20 second, use the default timer provided, so that worker remains responsive to the change
                if self.initiated is True and no_wait is False:
                    QtTest.QTest.qWait(self.wait_timer)
                    continue
                else:
                    break
            text = '\n'.join(text_data)
            self.setLabelTextandAdjust(text, initial_format=1)
            if no_wait is True:
                return
            for i in range(2000):
                QtTest.QTest.qWait(100)
                if self.format != 1:
                    break
        elif self.format == 2:
            for _ in range(30):
                if _ == 29:
                    return
                # For waiting 20 second, use the default timer provided, so that worker remains responsive to the change
                if self.initiated is True and no_wait is False:
                    QtTest.QTest.qWait(self.wait_timer)
                    continue
                else:
                    break
            teams_scorecard = text_data['score_strip']
            first_team = teams_scorecard[0]
            second_team = teams_scorecard[1]
            overs_timeline = text_data['overs_timeline']
            run_rate = first_team["run_rate"].replace('Run rate ', 'RR:') if first_team["run_rate"] else second_team["run_rate"].replace('Run rate ', 'RR:')
            if text_data['match_status'] == 'live':
                loader = " • "
            elif text_data['match_status'] == 'pre':
                loader = " * "
            elif text_data['match_status'] == 'post':
                loader = " 🦟 "
            else:
                loader = " "
            total_text_list = first_team["short_name"] + ":" + first_team["score"] + "\n" + second_team["short_name"] + ":" \
                + second_team["score"] + "\n" + run_rate + loader
            text_list = total_text_list + ','.join(overs_timeline[0]) if overs_timeline else total_text_list
            text = text_list.replace('<br>', '\n')

            if no_wait is True:
                self.setLabelTextandAdjust(text, initial_format=2)
                return
            self.loader(text, format=2, url=url, no_wait=no_wait)

    def refresh(self):
        self.restore_layout()
        # Reduce wait timer, to make already executing runner responsive
        self.wait_timer = 50
        # Wait 100 milisecond before triggering refresh
        QtTest.QTest.qWait(100)
        # Restore proper values
        self.wait_timer = 700
        self.initiating = False
        self.initiated = False

    def run(self):
        while True:
            try:
                self.trigger_per_format()
            except Exception as e:
                print(str(e))
                logging.exception(e)
                # self.refresh()


def fetch_clicked_line(workerThread, line, source_obj):
    workerThread.fetch_from_link(line=line, source_obj=source_obj)


def scrollWheelEvent(workerThread, scroll_direction):
    initiated = workerThread.is_initiated()
    if initiated is False and scroll_direction == 'down':
        workerThread.go_back()
    elif initiated is True and scroll_direction == 'up':
        workerThread.restore_layout()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = MyMainWindow(workerThread=WorkerThread, sides=(175, 82), mouseClickCallable=fetch_clicked_line,
                              scrollWheelCallable=scrollWheelEvent, up_threshold=3, down_threshold=5)
    MainWindow.show()
    sys.exit(app.exec_())
