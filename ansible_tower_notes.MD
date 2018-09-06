
EXTRA VARS:

SN_GROUPS: "os,managed_by,u_server_mgmt_type,operational_status"
SN_FIELDS: "os,managed_by, host_name, operational_status, u_server_mgmt_type"
SN_SEL_ORDER: "host_name"
SN_PROXY: https://webproxy.foo.net:3128/


# SN_Feilds are the host vars you want the script to bring into Tower
# SN_Groups defines your inventory groups based off host var returned
# SN_SEL_ORDER defines how to list the hosts in Tower
# SN_PROXY allows you to add your proxy



Custome Credential:

# created custom credential type with 3 feilds
# SN_USERNAME
# SN_PASSWORD
# SN_INSTANCE



input config
YAML
```
fields:
  - type: string
    id: username
    label: SN_USERNAME
  - secret: true
    type: string
    id: password
    label: SN_PASSWORD
  - type: string
    id: instance
    label: SN_INSTANCE
 ```
 JSON
 ```
 {
 "fields": [
  {
   "type": "string",
   "id": "username",
   "label": "SN_USERNAME"
  },
  {
   "secret": true,
   "type": "string",
   "id": "password",
   "label": "SN_PASSWORD"
  },
  {
   "type": "string",
   "id": "instance",
   "label": "SN_INSTANCE"
  }
 ]
}
```


 
 injector config
 
 YAML
 ```
 env:
  SN_INSTANCE: '{{instance}}'
  SN_PASSWORD: '{{password}}'
  SN_USERNAME: '{{username}}'
```
JSON
```
{
 "env": {
  "SN_INSTANCE": "{{instance}}",
  "SN_PASSWORD": "{{password}}",
  "SN_USERNAME": "{{username}}"
 }
}
```
