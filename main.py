from ast import While
from re import A
from attr import asdict
from pyrogram import Client, filters
from pyrogram.types import InputMediaPhoto, InputMediaVideo
import requests
import json
import sys, os
import asyncio
import aiohttp
import traceback
import sqlite3
import time
import io, base64
from PIL import Image

# Settings
api_id = '11284432'
api_hash = 'f94fe34d1d0d5d968955508f3b91b3c4'
last_error = None
sessions_path = os.path.dirname(sys.argv[0]) + '\sessions\\'
# 11284432
# f94fe34d1d0d5d968955508f3b91b3c4


def exit():
  sys.exit(0)

# Playground



# Sql
def qFetch(query):
  records = False
  try:
    print("qFetch: " + query)
    cursor = dbConnect.cursor()

    cursor.execute(query)
    # dbConnect.commit()
    # records = cursor.fetchall()    
    # cursor.close()
    # records = list(records)
    # print(records)

    records = cursor.fetchall()
    insertObject = []
    columnNames = [column[0] for column in cursor.description]

    for record in records:
      insertObject.append( dict( zip( columnNames , record ) ) )  

    records = insertObject

  except sqlite3.Error as error:
    print("SQLite fail", error)
    return False
  finally:
    print("SQLite success")
    return records

def qInsert(query):
  try:
    print("qInsert: " + query)
    cursor = dbConnect.cursor()

    cursor.execute(query)
    dbConnect.commit()
    # records = cursor.fetchall()
    cursor.close()

  except sqlite3.Error as error:
    print("SQLite fail", error)
    return False
  finally:
    print("SQLite success")
    return True

def qUpdate(query):
  try:
    print("qUpdate: " + query)
    cursor = dbConnect.cursor()

    cursor.execute(query)
    dbConnect.commit()
    # records = cursor.fetchall()
    cursor.close()

  except sqlite3.Error as error:
    print("SQLite fail", error)
    return False
  finally:
    print("SQLite success")
    return True

def qv(value):
  return "'" + str(value) + "'"

# Work
class Work:

  #Work
  works = []

  #Parse
  parseDelay = 10;
  parseNextAt = 0;

  def __init__(self):
    pass

  def parse(self):

    # Check delay
    if(time.time() < self.parseNextAt): return False

    # Get works
    r = session.get("http://t-spam-bot.loc/p/api", params={'api':'get'})
    self.works = json.loads(r.text)
    
    # Set delay
    self.parseNextAt = time.time() + self.parseDelay

    # Puts
    self.puts(self.works)

    # Send got
    workIds = []
    for work in self.works:
      workIds.append(work['id'])
    self.sendGot(workIds)

    return True

  def done(self, work, response):
    now = int(time.time())
    doneAt = qv(now)
    qUpdate( 'UPDATE "works" SET "done_at"=' + doneAt + ' WHERE  "id"=' + str(work['id']) )

    self.sendDone(work['id'], now, response)

  def sendGot(self, workIds):
    workIds = json.dumps(workIds)
    r = session.get("http://t-spam-bot.loc/p/api", params={'api':'got', 'workIds':workIds})

  def sendDone(self, workId, doneAt, response):
    params = {'api':'done', 'id':workId, 'done_at': doneAt, 'response':response }
    print('**done ')
    print(params)
    r = session.post("http://t-spam-bot.loc/p/api", data=params)
    print(r)

  # SQL
  def getActual(self):
    # Get work
    query = """ SELECT * FROM `works` WHERE `done_at` IS NULL ORDER BY "priority" DESC, "created_at" DESC LIMIT 1 """
    result = qFetch(query) 
    if(len(result) == 0): return False
    work = result[0]

    # Get properties    
    work['properties'] = {}
    query = 'SELECT * FROM `properties` WHERE `work_id` = ' + str(work['id'])
    result = qFetch(query) 
    if(len(result) == 0): return work
    properties = result
    for property in properties:
      # work['properties'].append({property['name'] : property['value']})

      # Images
      if property['name'] == 'image' :
        if 'images' in work['properties']:
          pass
        else:
          # create images
          work['properties']['images'] = []

        work['properties']['images'].append(property['value'])
        continue

      # Other
      work['properties'][property['name']] = property['value']

    return work

  def put(self, work): 
    # Check exists
    if(self.exists(work['id'])): 
      return False
    # Query
    keys = '"id", "function", "account", "status", "priority", "created_at", "got_at"'
    values = qv(work['id'])+","+qv(work['function'])+","+qv(work['account'])+","+qv(work['status'])+","+qv(work['priority'])+","+qv(work['created_at'])+","+qv(int(time.time()))
    query = 'INSERT INTO "works" ('+keys+') VALUES ('+values+');'
    qInsert(query)

    if "properties" in work:
      for proporty in work['properties']:
        keys = '"id", "work_id", "name", "value"'
        values = qv(proporty['id'])+","+qv(work['id'])+","+qv(proporty['name'])+","+qv(proporty['value'])
        query = 'INSERT INTO "properties" ('+keys+') VALUES ('+values+');'
        qInsert(query)

  def puts(self, works):
    for work in works:
      self.put(work)      

  def exists(self, id):
    works = qFetch('SELECT id FROM "works" WHERE id = '+str(id))
    if(len(works) > 0): return True;
    else: return False;

# Telegram
class Telegram:

  apps = []

  def __init__(self):
    pass

  def do(self, work):
    print('**do ' + work['function'] + ' ' + work['account'])
    app = self.getApp(work['account'])
    function = work['function']

    try:
      match function:
        case "login":
          r = self.login(app, work['account'])
        case 'signIn':
          r = self.signIn(app, work)
        case 'join_chat':
          chatId = work['properties']['chat_id'].replace("https://t.me/", "")
          chatId = chatId.replace("/", "")

          print('**join ' + chatId)
          r = app.join_chat(chat_id=chatId)
        case 'send_message':
          chatId = work['properties']['chat_id'].replace("https://t.me/", "")
          chatId = chatId.replace("/", "")
          text = work['properties']['text']
          print('**send ' + chatId)

          
          if 'images' in work['properties']:
            i = 0
            media = []
            for image in work['properties']['images']:                
              img = Image.open(io.BytesIO(base64.decodebytes(bytes(image, "utf-8"))))
              imgsrc = 'temp/'+str(i)+'.png'
              img.save(imgsrc)
              media.append(InputMediaPhoto(imgsrc))
              i = i + 1
            media[len(media) - 1] = InputMediaPhoto(imgsrc, caption=text)

            r = app.send_media_group(
              chat_id = chatId,
              media = media
            )
          else:
            r = app.send_message(chat_id=chatId, text=text)


          
          
        case _:
          r = 'bad function'
    except Exception as e:
      r = e



    print(r)
    return r


  #Login
  def isLoged(self, app):
    #Get me
    get_me = False
    me = False
    try:
      me = app.get_me()
    except Exception as e:
      get_me = e
    else:
      get_me = True

    # Work errors
    if get_me != True:
      if str(get_me).find("[401 AUTH_KEY_UNREGISTERED]") > -1:
        return -1
      if str(get_me).find("[401 SESSION_REVOKED]") > -1:
        return -1

    if get_me == True: return 1

    return 0    

  def login(self, app, account):

    # Check login
    isLogedResponse = self.isLoged(app)

    # Do login
    if(isLogedResponse == -1):
      return app.send_code(account)

    if(isLogedResponse == 1):
      return 'already login'

    return False
  
  def signIn(self, app, work):
    try:
      r = app.sign_in(phone_number=work['account'], phone_code_hash=work['properties']['phone_code_hash'], phone_code=work['properties']['code'],)
    except Exception as e:
      r = e

    return r

  def newApp(self, account):
    print('**new app ' + account)
    app = Client(sessions_path + account, api_id, api_hash)
    app.connect()
    self.apps.append({'account':account,'app':app})
    return app

  def getApp(self, account):
    app = False

    # Find from exists
    for a in self.apps:
      if(a['account'] == account):
        app = a['app']
        break
    
    # Start new app
    if(app == False):
      app = self.newApp(account)
    
    return app

# Login
def sendCode(acc):
  sent_code_info = acc['app'].send_code(acc['phone'])

  # sent_code_info = json.loads(sent_code_info)

  print(sent_code_info)

# Other
def sleep(x):
  time.sleep(x)



# Setup
dbConnect = sqlite3.connect('db/data.db')
session = requests.Session()

def mainLoop():

  work = Work()
  telegram = Telegram()

  while 1:

    # Parse
    print('**Parse works')
    work.parse()

    # Get actual
    print('**Get actual work')
    actualWork = work.getActual()
    if(actualWork == False):
      # Sleep
      print('**No works sleep')
      sleep(10)
      session.get("http://t-spam-bot.loc/crone")
      continue
    
    # Do
    response = telegram.do(actualWork)
    work.done(actualWork, response)



# Run
if __name__ == '__main__':

  mainLoop()



  # Playground


  # data = qFetch('SELECT * FROM properties')

  # print(data[0]['value'])
  # base64_str = data[0]['value']

  # import io, base64
  # from PIL import Image
  # img = Image.open(io.BytesIO(base64.decodebytes(bytes(base64_str, "utf-8"))))
  # img.save('my-image.png')

  # imgsrc = 'my-image.png'
  
  

  # phone_number = '+380992416157'
  # phone_number = '+37128885282'
  # app = Client(sessions_path + phone_number, api_id, api_hash)
  # app.start()
  

  # a = app.send_message("juge_play", "hi")

  # print(InputMediaPhoto(img))

  # a = app.send_media_group(
  #   chat_id = "juge_play",
  #   media = [
  #     InputMediaPhoto(imgsrc),
  #     InputMediaPhoto(imgsrc),
  #     InputMediaPhoto(imgsrc, caption="photo caption2")
  #   ]
  # )

  # a = app.get_history("me")

  # print(a)

  # loged = isLoged(app)

  # if loged == 1:
  #   print('loged!')
  # elif loged == 2:
  #   print('to login')

  #   sendCode({'app':app, 'phone': phone_number})


  # else:
  #   print('shit')


  # print(app.get_me())


  # app.stop()