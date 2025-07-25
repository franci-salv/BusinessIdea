import json
### DO NOT FORGET event = json.load(f) HAS TO BE CHANGED TO event = json.loads(f)     right now it only works because its another file 
with open('eventPractice.json','r') as f:
    event = json.load(f)


def get_phone():
    phone = event["phone_number_collection"]
    return phone

def Check_Db(phone):


