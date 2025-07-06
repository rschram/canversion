#!/usr/bin/python

###
# Reset Canvas site
#

import requests

name = 'reset'
token = "3156~3il8NVGXANrMRf1eOGalMFyG52kkHksebmNKBuRzn6D6zxVIpZUI4DJwrrcBWiu1"
server = "https://canvas.sydney.edu.au"
id = "65737"

header = {'Authorization': 'Bearer ' + '%s'%(token)}
url = str(server) + '/api/v1/courses/' + str(id) + '/reset_content' 
r = requests.delete(url=url, headers=header)
print(url)
print(header)
print(r)
print("Canvas site reset.")
