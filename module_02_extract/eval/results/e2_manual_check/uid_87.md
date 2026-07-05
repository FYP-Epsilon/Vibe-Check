# uid 87

## Gold nodes

-   g1  block    devices = Microsoft_Entra_ID_Devices__4_0_0__retrievewithwhere_Devices(devices_isCompliant_0=devices_isCompliant_0, devices_isCompliant_1=devices_isCompliant_1)
-   g2  loop     for device in devices
-   g3  gateway  not device['isCompliant']
-   g4  block    email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
-   g5  return   return None

## Gold edges

- g3 --true--> g4
- g2 --enter--> g3
- g4 --back--> g2
- g3 --back--> g2
- g1 --seq--> g2
- g2 --seq--> g5

## Extracted nodes

-     node_1  block    devices = Microsoft_Entra_ID_Devices__4_0_0__retrievewithwhere_Devices(devices_isCompliant_0=devices_isCompliant_0, devices_isCompliant_1=devices_isCompliant_1)
-     node_2  loop     iter devices
-     node_3  block    
-     node_4  gateway  not device['isCompliant']
-     node_5  block    email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
-     node_6  block    
-     node_7  block    
-     node_8  return   return None

## Extracted edges

- node_4 --not device['isCompliant']--> node_5
- node_4 --not (not device['isCompliant'])--> node_6
- node_5 ----> node_7
- node_6 ----> node_7
- node_2 --next(devices)--> node_4
- node_2 --exhausted(devices)--> node_3
- node_7 ----> node_2
- node_1 ----> node_2
- node_3 ----> node_8
