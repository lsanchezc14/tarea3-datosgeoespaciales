#!/usr/bin/env python
# coding: utf-8

# # Tarea 3
# ## Luis Sanchez - A65285
# 
# - [Enlace al codigo fuente en GitHub](https://github.com/lsanchezc14/tarea3-datosgeoespaciales/blob/main/Tarea3-LuisSanchez-A65285.ipynb)
# - [Enlace al codigo fuente en GitHub Version .py]()

# In[1]:


#Importar bibliotecas
import os
import requests
import zipfile

import pandas as pd
import geopandas as gpd
import json
from shapely.geometry import Point, mapping, shape, Polygon, LineString
import folium

from owslib.wfs import WebFeatureService
from geojson import dump

import plotly.express as px

import warnings
warnings.filterwarnings('ignore')


# In[2]:


url_cantones = 'https://geos.snitcr.go.cr/be/IGN_5/wfs?'
url_red_vial = 'https://geos.snitcr.go.cr/be/IGN_200/wfs?version=1.1.0'

wfs_cantones = WebFeatureService(url=url_cantones)
wfs_red_vial = WebFeatureService(url=url_red_vial)


# In[3]:


#Contenido del WFS escala 1:5000
list(wfs_cantones.contents)


# In[4]:


#Contenido del WFS escala 1:200 000
list(wfs_red_vial.contents)


# In[5]:


# Primero, los límites cantonales
params_cantones = dict(service='WFS',
              request='GetFeature', 
              typeName='IGN_5:limitecantonal_5k', #Capa de cantones a escala 1:5000
              srsName='urn:ogc:def:crs:EPSG::4326', #Coordenadas en WGS 84 
              outputFormat='json')

#Se convierte en formato json
capa_cantones_json = requests.get(url_cantones, params=params_cantones, verify=False).json()

#Se convierte también en Dataframe
response_cantones = requests.Request('GET',url_cantones, params=params_cantones).prepare().url
cantones = gpd.read_file(response_cantones)
columns_drop_cantones = ['id','gmlid', 'cod_catalo', 'cod_canton', 'ori_toponi', 'cod_provin', 'version']
cantones = cantones.drop(columns=columns_drop_cantones)


# In[6]:


# Segundo, la red vial
params_red = dict(service='WFS',
              request='GetFeature', 
              typeName='IGN_200:redvial_200k', #Capa de red vial a escala 1:200 000
              srsName='urn:ogc:def:crs:EPSG::4326', #Coordenadas en WGS 84
              outputFormat='json')

#Se convierte en formato json
capa_red_json = requests.get(url_red_vial, params=params_red, verify=False).json()

#Se convierte también en Dataframe
response_red = requests.Request('GET',url_red_vial, params=params_red).prepare().url
red_vial = gpd.read_file(response_red)

columns_drop_red = ['origen', 'codigo', 'num_ruta', 'jerarquia', 'nombre',
       'num_carril', 'mat_supe', 'est_supe', 'condi_uso', 'administra',
       'fiabilidad', 'num_carr', 'estac_peaj', 'id', 'tipo',
       'et_id', 'et_source', 'fid_', 'entity', 'handle', 'layer', 'lyrfrzn',
       'lyrlock', 'lyron', 'lyrvpfrzn', 'lyrhandle', 'color', 'entcolor',
       'lyrcolor', 'blkcolor', 'linetype', 'entlinetyp', 'lyrlntype',
       'blklinetyp', 'elevation', 'thickness', 'linewt', 'entlinewt',
       'lyrlinewt', 'blklinewt', 'refname', 'ltscale', 'extx', 'exty', 'extz',
       'docname', 'docpath', 'doctype', 'docver']

red_vial = red_vial.drop(columns=columns_drop_red)


# In[7]:


# Métodos auxiliares para convertir coordenadas en tuplas

def convertir_coordenadas_tuplas(coordenadas,tipo):
    len_coordenadas = len(coordenadas)
    
    if(tipo=='canton'):
        if(len_coordenadas==1):
            for i in coordenadas:
                coordenadas_tuplas = [tuple(j) for j in i]
        else:
            for i in coordenadas:
                for j in i:
                    coordenadas_tuplas = [tuple(k) for k in j]
    else:  
        coordenadas_tuplas = [tuple(i) for i in coordenadas]
        
    return coordenadas_tuplas


# In[8]:


# Lógica para calcular aquellos tramos de carreteras que en verdad se encuentran dentro de cada cantón.

lista_rutas_coordenadas = []
lista_rutas_categorias = []

for i in range(len(capa_cantones_json["features"])):
    #Iteración por cada cantón
    canton_coordenadas = convertir_coordenadas_tuplas(capa_cantones_json["features"][i]["geometry"]["coordinates"],'canton')
    canton = Polygon(canton_coordenadas)

    for j in range(len(capa_red_json["features"])):  
        #Iteración por cada ruta        
        ruta_coordenadas = convertir_coordenadas_tuplas(capa_red_json["features"][j]["geometry"]["coordinates"],'ruta')
        ruta = LineString(ruta_coordenadas)
        
        if canton.intersects(ruta):
            # intersection proporciona una buena aproximación de la ruta recortada dentro del poligono
            interseccion_resultante = canton.intersection(ruta)
            lista_rutas_coordenadas.append(interseccion_resultante)
            lista_rutas_categorias.append(capa_red_json["features"][j]["properties"]["categoria"])


# In[9]:


# Se convierte la lista en un objeto GeoSeries y luego un GeoDataFrame
# Se agregan al GeoFataFrame la columna de longitud y categoria

geo_lista = gpd.GeoSeries(lista_rutas_coordenadas)
geo_data = gpd.GeoDataFrame(geo_lista, columns = ['geometry'])
geo_data['longitud'] = gpd.GeoSeries(geo_data['geometry']).length*100000
geo_data['categoria'] = gpd.GeoSeries(lista_rutas_categorias)


# In[10]:


# Se hace un join espacial del DataFrame cantones y geo_data
# El join conserva todas las rutas "right join"

join_espacial = gpd.sjoin(cantones,geo_data, how="right",op="intersects")
longitud_agrupada = join_espacial.groupby('canton')['longitud'].sum()

#Se calcula la densidad y se agrega como columna

cantones_sorted = cantones.sort_values(by=['canton'], ascending=True)
cantones_sorted = cantones_sorted.assign(longitud_total=longitud_agrupada.values/1000)
cantones_sorted['densidad_total'] = cantones_sorted.apply(lambda row: row.longitud_total / row.area, axis=1)


# In[11]:


longitud_sin_pavimento = join_espacial.query('categoria=="CARRETERA SIN PAVIMENTO DOS VIAS"').groupby('canton')['longitud'].sum()/1000
longitud_pavimento_1 = join_espacial.query('categoria=="CARRETERA PAVIMENTO UNA VIA"').groupby('canton')['longitud'].sum()/1000
longitud_pavimento_2 = join_espacial.query('categoria=="CARRETERA PAVIMENTO DOS VIAS O MAS"').groupby('canton')['longitud'].sum()/1000
longitud_camino_tierra = join_espacial.query('categoria=="CAMINO DE TIERRA"').groupby('canton')['longitud'].sum()/1000
longitud_autopista = join_espacial.query('categoria=="AUTOPISTA"').groupby('canton')['longitud'].sum()/1000


# In[12]:


# Se imprimen las longitudes por categoría y se hace una validación cruzada para
# confirmar que las distancias calculadas se aproximan a las suministradas por el conjunto de datos original

print("Longitud total calculada 'CARRETERA SIN PAVIMENTO DOS VIAS' = "+str(longitud_sin_pavimento.sum()))
print("Longitud total calculada 'CARRETERA PAVIMENTO UNA VIA' = "+str(longitud_pavimento_1.sum()))
print("Longitud total calculada 'CARRETERA PAVIMENTO DOS VIAS O MAS' = "+str(longitud_pavimento_2.sum()))
print("Longitud total calculada 'CAMINO DE TIERRA' = "+str(longitud_camino_tierra.sum()))
print("Longitud total calculada 'AUTOPISTA' = "+str(longitud_autopista.sum()))

print("Longitud total datos crudos 'CARRETERA SIN PAVIMENTO DOS VIAS' = "
      +str(red_vial.loc[red_vial['categoria'] == 'CARRETERA SIN PAVIMENTO DOS VIAS', 'longitud'].sum()/1000))
print("Longitud total datos crudos 'CARRETERA PAVIMENTO UNA VIA' = "
      +str(red_vial.loc[red_vial['categoria'] == 'CARRETERA PAVIMENTO UNA VIA', 'longitud'].sum()/1000))
print("Longitud total datos crudos 'CARRETERA PAVIMENTO DOS VIAS O MAS' = "
      +str(red_vial.loc[red_vial['categoria'] == 'CARRETERA PAVIMENTO DOS VIAS O MAS', 'longitud'].sum()/1000))
print("Longitud total datos crudos 'CAMINO DE TIERRA' = "
      +str(red_vial.loc[red_vial['categoria'] == 'CAMINO DE TIERRA', 'longitud'].sum()/1000))
print("Longitud total datos crudos 'AUTOPISTA' = "
      +str(red_vial.loc[red_vial['categoria'] == 'AUTOPISTA', 'longitud'].sum()/1000))


# In[13]:


# Se convierten estas longitudes en DataFrame

data_longitud_sin_pavimento = pd.DataFrame({'canton':longitud_sin_pavimento.index,
                                          'longitud_sin_pavimento':longitud_sin_pavimento.values})
data_longitud_pavimento_1 = pd.DataFrame({'canton':longitud_pavimento_1.index,
                                          'longitud_pavimento_1':longitud_pavimento_1.values})
data_longitud_pavimento_2 = pd.DataFrame({'canton':longitud_pavimento_2.index,
                                          'longitud_pavimento_2':longitud_pavimento_2.values})
data_longitud_camino_tierra = pd.DataFrame({'canton':longitud_camino_tierra.index,
                                          'longitud_camino_tierra':longitud_camino_tierra.values})
data_longitud_autopista = pd.DataFrame({'canton':longitud_autopista.index,
                                          'longitud_autopista':longitud_autopista.values})


# ## 1. Tabla con información sobre los 82 cantones

# In[14]:


# Se agregan al DataFrame una columna por tipo/categoría de carretera

cantones_sorted = cantones_sorted.merge(data_longitud_sin_pavimento, on='canton', how='left')
cantones_sorted = cantones_sorted.merge(data_longitud_pavimento_1, on='canton', how='left')
cantones_sorted = cantones_sorted.merge(data_longitud_pavimento_2, on='canton', how='left')
cantones_sorted = cantones_sorted.merge(data_longitud_camino_tierra, on='canton', how='left')
cantones_sorted = cantones_sorted.merge(data_longitud_autopista, on='canton', how='left')

columnas_rellenar = ['longitud_sin_pavimento', 'longitud_pavimento_1', 'longitud_pavimento_2', 'longitud_camino_tierra', 'longitud_autopista']

cantones_sorted[columnas_rellenar] = cantones_sorted[columnas_rellenar].fillna(0) # Se rellenan nulls con ceros


# In[15]:


pd.options.display.max_rows = 100
cantones_sorted.drop(columns=['geometry','provincia'])


# ## 2. Gráfico de barras apiladas: Los 15 cantones con mayor longitud de carreteras y su distribución por categoria de carretera

# In[16]:


# Se crea un DataFrame que solo tiene el top 15 de cantones segun su longitud total

cantones_top_15 = cantones_sorted.nlargest(n=15, columns=['longitud_total'])


# In[17]:


cantones_top_15


# In[18]:


#Se imprime el gráfico

fig = px.bar(cantones_top_15, x="canton",
             y=['longitud_sin_pavimento','longitud_pavimento_1',
                                             'longitud_pavimento_2','longitud_camino_tierra','longitud_autopista'],
            labels={
                "value": "Distancia (km)",
                "canton": "Cantones",
                "longitud_sin_pavimento": "Sin pavimento de dos vías",
                "longitud_pavimento_1": "De pavimento de una vía",
                "longitud_pavimento_2": "De pavimento de dos vías o más",
                "longitud_camino_tierra": "Caminos de tierra",
                "longitud_autopista": "Autopistas",
                "variable":"Tipos de carreteras"
            },
             title="Distribución por tipo de carretera en los 15 cantones con más longitud total")
fig.show()


# ## 3. Gráfico de pastel: Proporción de los 15 cantones con mayor longitud de carreta y "otros cantones"

# In[19]:


# Se calcula otros cantones y se agrega al DataFrame

otros_cantones = {'canton':'Otros cantones', 'longitud_total':cantones_sorted['longitud_total'].sum()-cantones_top_15['longitud_total'].sum()}
cantones_top_16 = cantones_top_15.append(otros_cantones, ignore_index=True)


# In[20]:


fig = px.pie(cantones_top_16, values='longitud_total', names='canton',
             title='Proporción de los 15 cantones con mayor longitud de carreta y "otros cantones"')
fig.show()


# ## 4. Mapa Folium con capas: densidad vial y red vial

# In[21]:


# Creación del mapa base de folium
m = folium.Map(location=[9.8, -84], tiles='CartoDB positron', zoom_start=8, control_scale=True)

# Creación de la capa de coropletas
folium.Choropleth(
    name="Densidad vial",
    geo_data=cantones_sorted,
    data=cantones_sorted,
    columns=["canton","densidad_total"],
    bins=7,
    key_on="feature.properties.canton",
    fill_color="Reds",
    fill_opacity=0.5, 
    line_opacity=1,
    legend_name="Densidad (Longitud/Area)",
).add_to(m)


# Se añade la capa de red vial
folium.GeoJson(data=capa_red_json,
               name='Red vial'
              ).add_to(m)

folium.LayerControl().add_to(m)

m

