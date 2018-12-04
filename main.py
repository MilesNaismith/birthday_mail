import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
import smtplib
from email.mime.text import MIMEText
import schedule
import time
import daemon
import settings

# Изменяем тип со строки на datetime
def birthday_date(birthday):
    try:
        birthday = birthday.split('.')
        for i in range(len(birthday)):
            birthday[i] = int(birthday[i])                
        today = date.today()
        birthday = date(year = today.year, month = birthday[1], day = birthday[0])    
    except ValueError:
        birthday = None  
    return birthday

# Готовоим текст письма с именинниками
def birthday_text(birthday_list):
    text = "Внимание! В ближайшее время День Рождения у следующих людей:\n\r"
    for user in birthday_list:
        text = text + "{}, день рождения {}\n\r".format(user[0],user[1])
    return text

# Отправка писем
def mail_send(email, text):
    HOST = settings.IMAP_SERVER_HOST_NAME
    SUBJECT = "Дни Рождения"
    TO = email
    FROM = "noreply@mts-it.ru"
    msg = MIMEText(text.encode('utf-8'), 'plain', 'UTF-8')
    msg['From'] = FROM
    msg['To'] = TO
    msg['Subject'] = SUBJECT
    server = smtplib.SMTP(HOST)
    server.sendmail(FROM, [TO], msg.as_string())
    server.quit()

# Парсинг и сбор данных с таблицы
def table_parcing():
    users = []
    url = '{}rest/api/content/search?cql=space={}'.format(settings.CONFLUENCE_CONNECTION_STRING, settings.CONFLUENCE_SPACE)
    headers = {'login_username': settings.CONFLUENCE_USER,
            'login_password': settings.CONFLUENCE_PASSWORD}
    page = requests.get(url=url,
                        params={'expand': 'body.storage'}, 
                        auth=(headers['login_username'], headers['login_password']))
    page = page.json()   
    res = page['results']
    for value in res:
        if value['id'] == settings.CONFLUENCE_PAGE_ID:
            result = value                        
    html = result['body']['storage']['value']
    soup = BeautifulSoup(html)
    table = soup.find("table",{"class":"relative-table wrapped"})
    table_body = table.find("tbody")
    rows = table_body.find_all("tr")
    for row in rows:
        user = []
        cells = row.find_all("td")
        for cell in cells:
            user.append(cell.text)
        users.append(user)

    users_temp = users[1:]
    users = []
    for user in users_temp:
        user_content = {'id': user[0], 
                    'name': user[1], 
                    'position': user[2], 
                    'fullname': user[3], 
                    'email': user[4], 
                    'phone_number': user[5], 
                    'birthday': user[6], 
                    'AD_login': user[7], 
                    'room': user[8],
                    }
        users.append(user_content)
    return users

def main():
    # Собираем список именинников
    users = table_parcing()
    for user in users:
        user['birthday'] = birthday_date(user['birthday'])              
    birthday_people = []
    birthday_people_emails = []
    for user in users:
        try:
            time = user['birthday'] - date.today()
            delta1 = timedelta(days = 7)
            delta2 = timedelta(days = -1)
            if  time <= delta1 and time >= delta2 and user['room'] != 'уволен':
                birthday_people.append([user['fullname'], datetime.strftime(user['birthday'], "%d.%m.%y"), user['email']])
                birthday_people_emails.append(user['email'])
        except (TypeError, ValueError):
            pass
    # Проверка, есть ли именинника       
    if len(birthday_people) == 0:
        return "No birthdays"
    # Рассыка email'ов по списку    
    for user in users:
        if user['email'] is None or user['room'] == 'уволен':
            continue
        elif user['email'] not in birthday_people_emails:
            text = birthday_text(birthday_people)
            mail_send(user['email'], text)    
        else:
            birthday_people_except = []
            for birthday_user in birthday_people:
                if user['email'] != birthday_user[2]:
                    birthday_people_except.append(birthday_user)
            if len(birthday_people_except) > 0:        
                text = birthday_text(birthday_people_except)
                mail_send(user['email'], text)

# Расписание запуска
def sheduler():
    schedule.every().monday.at(settings.SENDING_TIME).do(main)
    schedule.every().tuesday.at(settings.SENDING_TIME).do(main)
    schedule.every().wednesday.at(settings.SENDING_TIME).do(main)
    schedule.every().thursday.at(settings.SENDING_TIME).do(main)
    schedule.every().friday.at(settings.SENDING_TIME).do(main)
    while True:
        schedule.run_pending()
        time.sleep(1)

# Демонизация
with daemon.DaemonContext():
    sheduler()