import datetime
import json
import logging
import os
import requests
import sched
import sys
import threading
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException as WebDriverException
from selenium.common.exceptions import NoSuchElementException as NoSuchElementException

logger = logging.getLogger(__name__)

config = {
    'ww_api_key': '',
    'ww_chromedriver_path': 'bin/chromedriver',
    'ww_colors': True,  # True/False. True prints colorful msgs in console   
    'ww_url': '',
    'ww_msg_interval': 5,  # Time (seconds). Recommended value: 5
    'ww_msg_update_url': '',
    'ww_msg_url': ''
}

# API end points
config['ww_url'] = os.getenv('WW_URL', config['ww_url'])
config['ww_msg_url'] = os.getenv('WW_MSG_URL', config['ww_msg_url']) + "?api_key=" + os.getenv('WW_API_KEY', config['ww_api_key'])
config['ww_msg_update_url'] = os.getenv('WW_MSG_UPDATE_URL', config['ww_msg_update_url']) + "?api_key=" + os.getenv('WW_API_KEY', config['ww_api_key'])

print ("Env")
print config['ww_url']

message_scheduler = sched.scheduler(time.time, time.sleep)
last_printed_msg_id = 0
last_thread_name = ''

# colors in console


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


try:
    def main():
        print 'Starting app...'
        # setting up Chrome with selenium
        ww_chromedriver_path = os.getenv(
            'ww_chromedriver_path', config['ww_chromedriver_path'])
        driver = webdriver.Chrome(ww_chromedriver_path)
        print '*********** Main engine launched **********'
        # open WW in browser
        ww_url = config['ww_url']
        driver.get(ww_url)

        # prompt user to connect device to WW
        while True:
            isConnected = raw_input("Phone connected? y/n: ")
            if isConnected.lower() == 'y':
                break

            assert "Openroad" in driver.title

        # start background thread
        message_thread = threading.Thread(
            target=startfetchMessages, args=(driver,))
        message_thread.start()

        while True:
            pass

    def sendMessage(driver, msg):
        """
        Type 'msg' in 'driver' and press RETURN
        """
        # select correct input box to type msg
        input_box = driver.find_element(
            By.XPATH, '//*[@id="main"]//footer//div[contains(@class, "_2S1VP")]')
        # input_box.clear()
        input_box.click()

        action = ActionChains(driver)
        action.send_keys(msg)
        action.send_keys(Keys.RETURN)
        action.perform()

    def startfetchMessages(driver):
        """
        Start schdeuler that gets messages every ww_msg_interval seconds
        """
        ww_msg_interval = int(config['ww_msg_interval'])
        message_scheduler.enter(
            ww_msg_interval, 1, fetchMessage, (driver, message_scheduler))
        message_scheduler.run()

    def fetchMessage(driver, scheduler):
        print("Fetching messages...")
        try:
            ww_msg_url = config['ww_msg_url']
            result = requests.get(ww_msg_url)
            data = result.json()

            if 'status' in data.keys():
                status = data['status']

                if status == 200:
                    messages = data['messages']

                    if messages:
                        for i in range(len(messages)):
                            # Preparing the message.
                            sms_id = messages[i]['id']
                            sms_receiver = messages[i]['receiver'].replace(
                                "+", "")
                            sms_receiver = sms_receiver.replace(" ", "")
                            sms_receiver_title = messages[i]['receiver']
                            sms_body = messages[i]['body']
                            sms_chat_found = messages[i]['chat_found']
                            sms_processed = messages[i]['processed']
                            sms_processed_at = messages[i]['processed_at']
                            sms_created_at = ""

                            # Replying.
                            # Selecting specific chat.
                            try:
                                print (sms_receiver)
                                chooseReceiver(driver, sms_receiver)
                                sendMessage(driver, sms_body)
                                data = {'message_id': sms_id, 'chat_found': '1', 'processed': '1'}

                            except NoSuchElementException as e:
                                # data = {'chat_found' : '2', 'processed' : '0'}
                                # print(decorateMsg("^-- Can not find this Receiver in the chat list.\n\n", bcolors.FAIL))
                                sendMessage(driver, sms_body)
                                data = {'message_id': sms_id, 'chat_found': '1', 'processed': '1'}

                            except WebDriverException as e:
                                data = {'message_id': sms_id, 'chat_found': '2', 'processed': '0'}
                                print(decorateMsg(
                                    "^-- Can not process this Receiver.\n\n", bcolors.FAIL))

                            # Update the message status.
                            result = requests.post(config['ww_msg_update_url'], data=data)
                            time.sleep(5)
                else:
                    print("There are no messages to process.\n")
            else:

                print 'API responded with {}'.format(data['detail'])

        except requests.exceptions.ConnectionError as conn_error:
            print "An error occured"
            print conn_error

        # add the task to the scheduler again
        ww_msg_interval = int(config['ww_msg_interval'])
        message_scheduler.enter(
            ww_msg_interval, 1, fetchMessage, (driver, scheduler))

    def decorateMsg(msg, color=None):
        """
        Returns:
                colored msg, if colors are enabled in config and a color is provided for msg
                msg, otherwise
        """
        msg_string = msg
        if config['ww_colors']:
            if color:
                msg_string = "{}{}{}".format(color, msg, bcolors.ENDC)

        return msg_string

    def printThreadName(driver):
        global last_thread_name
        curr_thread_name = driver.find_element(
            By.XPATH, '//*[@id="main"]/header//div[contains(@class, "chat-main")]').text
        if curr_thread_name != last_thread_name:
            last_thread_name = curr_thread_name
            print(decorateMsg("\n\tSending msgs to:",
                              bcolors.OKBLUE), curr_thread_name)
        return curr_thread_name

    def chooseReceiver(driver, receiver):
        input_box = driver.find_element(By.XPATH, '//*[@id="side"]//input')
        input_box.clear()
        input_box.click()
        input_box.send_keys(receiver)
        input_box.send_keys(Keys.RETURN)
        printThreadName(driver)

    if __name__ == '__main__':
        main()

except AssertionError as e:
    sys.exit(decorateMsg("\n\tCannot open web URL.", bcolors.WARNING))

except KeyboardInterrupt as e:
    sys.exit(decorateMsg("\n\tPress Ctrl+C again to exit.", bcolors.WARNING))

except WebDriverException as e:
    sys.exit()
