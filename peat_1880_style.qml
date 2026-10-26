<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40" styleCategories="Symbology|Fields|Forms">
  <renderer-v2 type="categorizedSymbol" attr="hist_type" symbollevels="0" enableorderby="0" forceraster="0" referencescale="-1">
    <categories>
      <category render="true" symbol="0" value="Moor" label="Moor" type="string"/>
      <category render="true" symbol="1" value="nasser Boden" label="nasser Boden" type="string"/>
      <category render="true" symbol="2" value="nasse Wiese" label="nasse Wiese" type="string"/>
      <category render="true" symbol="3" value="Heide" label="Heide" type="string"/>
    </categories>
    <symbols>
      <symbol type="fill" name="0" alpha="1" clip_to_extent="1" force_rhr="0" frame_rate="10" is_animated="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option type="QString" name="color" value="140,81,10,77"/>
            <Option type="QString" name="style" value="solid"/>
            <Option type="QString" name="outline_color" value="140,81,10,255"/>
            <Option type="QString" name="outline_style" value="solid"/>
            <Option type="QString" name="outline_width" value="0.5"/>
            <Option type="QString" name="outline_width_unit" value="MM"/>
            <Option type="QString" name="joinstyle" value="bevel"/>
            <Option type="QString" name="border_width_map_unit_scale" value="3x:0,0,0,0,0,0"/>
            <Option type="QString" name="offset" value="0,0"/>
            <Option type="QString" name="offset_unit" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="1" alpha="1" clip_to_extent="1" force_rhr="0" frame_rate="10" is_animated="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option type="QString" name="color" value="1,102,94,77"/>
            <Option type="QString" name="style" value="solid"/>
            <Option type="QString" name="outline_color" value="1,102,94,255"/>
            <Option type="QString" name="outline_style" value="solid"/>
            <Option type="QString" name="outline_width" value="0.5"/>
            <Option type="QString" name="outline_width_unit" value="MM"/>
            <Option type="QString" name="joinstyle" value="bevel"/>
            <Option type="QString" name="border_width_map_unit_scale" value="3x:0,0,0,0,0,0"/>
            <Option type="QString" name="offset" value="0,0"/>
            <Option type="QString" name="offset_unit" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="2" alpha="1" clip_to_extent="1" force_rhr="0" frame_rate="10" is_animated="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option type="QString" name="color" value="33,102,172,77"/>
            <Option type="QString" name="style" value="solid"/>
            <Option type="QString" name="outline_color" value="33,102,172,255"/>
            <Option type="QString" name="outline_style" value="solid"/>
            <Option type="QString" name="outline_width" value="0.5"/>
            <Option type="QString" name="outline_width_unit" value="MM"/>
            <Option type="QString" name="joinstyle" value="bevel"/>
            <Option type="QString" name="border_width_map_unit_scale" value="3x:0,0,0,0,0,0"/>
            <Option type="QString" name="offset" value="0,0"/>
            <Option type="QString" name="offset_unit" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="3" alpha="1" clip_to_extent="1" force_rhr="0" frame_rate="10" is_animated="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option type="QString" name="color" value="118,42,131,77"/>
            <Option type="QString" name="style" value="solid"/>
            <Option type="QString" name="outline_color" value="118,42,131,255"/>
            <Option type="QString" name="outline_style" value="solid"/>
            <Option type="QString" name="outline_width" value="0.5"/>
            <Option type="QString" name="outline_width_unit" value="MM"/>
            <Option type="QString" name="joinstyle" value="bevel"/>
            <Option type="QString" name="border_width_map_unit_scale" value="3x:0,0,0,0,0,0"/>
            <Option type="QString" name="offset" value="0,0"/>
            <Option type="QString" name="offset_unit" value="MM"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <fieldConfiguration>
    <field name="hist_type" configurationFlags="NoFlag">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option type="List" name="map">
                <Option type="Map"><Option type="QString" name="Moor" value="Moor"/></Option>
                <Option type="Map"><Option type="QString" name="nasser Boden" value="nasser Boden"/></Option>
                <Option type="Map"><Option type="QString" name="nasse Wiese" value="nasse Wiese"/></Option>
                <Option type="Map"><Option type="QString" name="Heide" value="Heide"/></Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <constraints>
    <constraint field="hist_type" constraints="1" notnull_strength="1" unique_strength="0" exp_strength="0"/>
  </constraints>
  <layerGeometryType>2</layerGeometryType>
</qgis>
