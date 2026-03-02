<?xml version="1.0" encoding="UTF-8"?>
<!-- Smart Farm Simulation — 10 sensor nodes + 1 border router
     Grid layout: 2×5, 30m spacing
     Contiki-NG (org.contikios.cooja) -->
<simconf version="1.0">
  <simulation>
    <title>Smart Farm — 10 Sensors</title>
    <randomseed>123456</randomseed>
    <motedelay_us>1000000</motedelay_us>
    <radiomedium>
      org.contikios.cooja.radiomediums.UDGM
      <transmitting_range>50.0</transmitting_range>
      <interference_range>100.0</interference_range>
      <success_ratio_tx>1.0</success_ratio_tx>
      <success_ratio_rx>1.0</success_ratio_rx>
    </radiomedium>
    <events>
      <logoutput>40000</logoutput>
    </events>

    <!-- Border Router (node ID = 1) -->
    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <identifier>border_router</identifier>
      <description>Border Router</description>
      <source>[APPS_DIR]/../../cooja/firmware/border_router.c</source>
      <commands>make border_router.cooja TARGET=cooja CONTIKI=[CONTIKI_DIR]</commands>
      <firmware>[APPS_DIR]/../../cooja/firmware/border_router.cooja</firmware>
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.RimeAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.IPAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Mote2MoteRelations</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.MoteAttributes</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRS232</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiBeeper</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRadio</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiClock</moteinterface>
    </motetype>

    <!-- Sensor Nodes (IDs 2-11) -->
    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <identifier>sensor_node</identifier>
      <description>Smart Farm Sensor Node (Vendor A/B/C/D by node_id%%4)</description>
      <source>[APPS_DIR]/../../cooja/firmware/sensor_node.c</source>
      <commands>make sensor_node.cooja TARGET=cooja CONTIKI=[CONTIKI_DIR]</commands>
      <firmware>[APPS_DIR]/../../cooja/firmware/sensor_node.cooja</firmware>
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.RimeAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.IPAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Mote2MoteRelations</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.MoteAttributes</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRS232</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiBeeper</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRadio</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiClock</moteinterface>
    </motetype>

    <!-- Border Router at center -->
    <mote>
      <breakpoints/>
      <interface_config>
        org.contikios.cooja.interfaces.Position
        <x>75.0</x><y>75.0</y><z>0.0</z>
      </interface_config>
      <interface_config>
        org.contikios.cooja.contikimote.interfaces.ContikiMoteID
        <id>1</id>
      </interface_config>
      <motetype_identifier>border_router</motetype_identifier>
    </mote>

    <!-- Sensor nodes: 2×5 grid, 30m spacing, starting at (30,30) -->
    <!-- Row 0 -->
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>30.0</x><y>30.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>2</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>60.0</x><y>30.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>3</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>90.0</x><y>30.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>4</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>120.0</x><y>30.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>5</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>150.0</x><y>30.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>6</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <!-- Row 1 -->
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>30.0</x><y>60.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>7</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>60.0</x><y>60.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>8</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>90.0</x><y>60.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>9</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>120.0</x><y>60.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>10</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>150.0</x><y>60.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>11</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
  </simulation>
</simconf>
