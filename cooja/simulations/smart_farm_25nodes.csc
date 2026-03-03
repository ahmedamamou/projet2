<?xml version="1.0" encoding="UTF-8"?>
<!-- Smart Farm Simulation — 25 sensor nodes + 1 border router
     Grid layout: 5×5, 25m spacing
     Contiki-NG (org.contikios.cooja) -->
<simconf version="1.0">
  <simulation>
    <title>Smart Farm — 25 Sensors</title>
    <randomseed>123456</randomseed>
    <motedelay_us>1000000</motedelay_us>
    <radiomedium>
      org.contikios.cooja.radiomediums.UDGM
      <transmitting_range>40.0</transmitting_range>
      <interference_range>80.0</interference_range>
      <success_ratio_tx>1.0</success_ratio_tx>
      <success_ratio_rx>0.95</success_ratio_rx>
    </radiomedium>
    <events><logoutput>40000</logoutput></events>

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
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRS232</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRadio</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiClock</moteinterface>
    </motetype>

    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <identifier>sensor_node</identifier>
      <description>Smart Farm Sensor Node</description>
      <source>[APPS_DIR]/../../cooja/firmware/sensor_node.c</source>
      <commands>make sensor_node.cooja TARGET=cooja CONTIKI=[CONTIKI_DIR]</commands>
      <firmware>[APPS_DIR]/../../cooja/firmware/sensor_node.cooja</firmware>
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.RimeAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.IPAddress</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRS232</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRadio</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiClock</moteinterface>
    </motetype>

    <!-- Border Router at center (62.5, 62.5) -->
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>62.5</x><y>62.5</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>1</id></interface_config><motetype_identifier>border_router</motetype_identifier></mote>

    <!-- 5×5 grid: rows 0-4, cols 0-4, 25m spacing, origin (0,0) -->
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>0.0</x><y>0.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>2</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>25.0</x><y>0.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>3</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>50.0</x><y>0.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>4</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>75.0</x><y>0.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>5</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>100.0</x><y>0.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>6</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>0.0</x><y>25.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>7</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>25.0</x><y>25.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>8</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>50.0</x><y>25.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>9</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>75.0</x><y>25.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>10</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>100.0</x><y>25.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>11</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>0.0</x><y>50.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>12</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>25.0</x><y>50.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>13</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>50.0</x><y>50.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>14</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>75.0</x><y>50.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>15</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>100.0</x><y>50.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>16</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>0.0</x><y>75.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>17</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>25.0</x><y>75.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>18</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>50.0</x><y>75.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>19</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>75.0</x><y>75.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>20</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>100.0</x><y>75.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>21</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>0.0</x><y>100.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>22</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>25.0</x><y>100.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>23</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>50.0</x><y>100.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>24</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>75.0</x><y>100.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>25</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
    <mote><breakpoints/><interface_config>org.contikios.cooja.interfaces.Position<x>100.0</x><y>100.0</y><z>0.0</z></interface_config><interface_config>org.contikios.cooja.contikimote.interfaces.ContikiMoteID<id>26</id></interface_config><motetype_identifier>sensor_node</motetype_identifier></mote>
  </simulation>
</simconf>
