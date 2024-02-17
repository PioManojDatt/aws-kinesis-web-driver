from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from webdriver_manager.core.os_manager import ChromeType
import time, os, socket
import polling2 as polling
import logging
from dotenv import load_dotenv, set_key
load_dotenv()

chrome_options = webdriver.ChromeOptions()
# chrome_options.add_argument("--headless")
chrome_options.add_argument("use-fake-ui-for-media-stream")
prefs = {
    'profile.default_content_setting_values.automatic_downloads': 1,
    'profile.default_content_settings.popups': 0,
    'download.default_directory': os.path.join(os.getcwd(), 'recordings'),
    'directory_upgrade': True
}
chrome_options.add_experimental_option("prefs", prefs)
chrome_options.add_experimental_option("detach", True)
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

try:
    # Enable network events
    driver.execute_cdp_cmd('Network.enable', {})

    driver.get("http://localhost:5000")
    region = polling.poll(lambda: driver.find_element(By.ID , "region"), step=0.5, timeout=10)
    region.clear()
    region.send_keys(os.getenv('AWS_REGION'))
    # Set aws client id
    accessKeyId = driver.find_element(By.ID , "accessKeyId")
    accessKeyId.clear()
    accessKeyId.send_keys(os.getenv('AWS_CLIENT_ID'))
    # Set aws client secret key
    secretAccessKey = driver.find_element(By.ID , "secretAccessKey")
    secretAccessKey.clear()
    secretAccessKey.send_keys(os.getenv('AWS_SECRET_KEY'))
    # Set aws client secret key
    secretAccessKey = driver.find_element(By.ID , "secretAccessKey")
    secretAccessKey.clear()
    secretAccessKey.send_keys(os.getenv('AWS_SECRET_KEY'))
    # Set channel name
    channel_name = os.getenv('CHANNEL_NAME')
    if channel_name:
        channelName = driver.find_element(By.ID , "channelName")
        channelName.clear()
        channelName.send_keys(channel_name)
    else:
        # Set hostname as channel name
        channel_name = socket.gethostname()
        channelName = driver.find_element(By.ID , "channelName")
        channelName.clear()
        channelName.send_keys(channel_name)
        set_key('.env', 'CHANNEL_NAME', channel_name)
        time.sleep(1)
        # Trigger create channel
        channelButton = driver.find_element(By.ID , "create-channel-button")
        channelButton.click()
        time.sleep(5)
    # Start master view
    masterButton = driver.find_element(By.ID , "master-button")
    masterButton.click()
except Exception as ex:
    print(f"[Master WebDriver] Error # {ex}")
    driver.quit()