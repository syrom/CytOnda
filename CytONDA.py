#!/usr/bin/env python
# coding: utf-8

# # CytONDA: Organisational Network Discovery & Analysis


import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html

import plotly.graph_objs as go
import pandas as pd
from colour import Color
import dash_cytoscape as cyto
import json

# # 2) Variable declaration
new_line = '\n'
l_node_attribs4display = ['id', 'type', 'description']
l_edge_attribs4display = ['source', 'target', 'weight']

# # 3) Definitions
# ## 3a) Class definitions
# ## 3b) Function Definitions

def f_define_elements(nodes_data, edges_data, cl_node_description, cl_node_org, cl_node_type):
    # as prepartation for check in loop, further extend list with all nodes in the aux_set1 which have node_org that is NOT in the criterium list
    cl_node_org_extended = cl_node_org + ['C', 'P'] # Criterium List must be extended by acronyms for comptence and project as they CAN potentially be
                                                    # included in the node_type criterium list and would erroneously be filtered out again here
    # add 'H' (Hierarchy) in any case to the list of selected node types; otherwise, pure setting to Project or Competence do not trace back
    # to the individuals represented in the H-entries
    if 'H' not in cl_node_type:
        cl_node_type.append('H')    
    # BEFORE FIRST QUERY !!!! Otherwise problem thru C and P values in Orga-field

    # define query string
    s_query = 'NODE_TYPE in @cl_node_type and NODE_DESC in @cl_node_description and NODE_ORG in @cl_node_org_extended'
    df_nodes_filtered = df_nodes.query(s_query)

    l_nodes_aux1 = df_nodes_filtered.NODES.to_list()

    # Creating a set of edges where either SOURCE or TARGET node is equal to filtered nodes:
    # CAUTION: This set can still contain nodes that GO BEYOND THE FILTER CRITERIA  defined in the node types list
    # as ANY edge leading to one of the filtered nodes qualifies a non-filtered node to enter the set
    aux_set1 = set()
    for index in range(0,len(df_edges)):
        if (df_edges['SOURCE'][index] in l_nodes_aux1 or df_edges['TARGET'][index] in l_nodes_aux1):

            aux_set1.add(df_edges['SOURCE'][index])
            aux_set1.add(df_edges['TARGET'][index])

    # Removing unqualified nodes according to filter criteria:
    # Cleaning the set from all nodes that have a node type or belong to an organisation other than those defined in the node type and node orga filter list:
    # as prepartation for check in loop, further extend list with all nodes in the aux_set1 which have node_org that is NOT in the criterium list
    # create a list with all nodes in the aux_set1 which have node class or ORG that is NOT in the criterium list
    l_aux = []
    for i in aux_set1:
        if df_nodes.query('NODES == @i').empty:
            continue
        else:
            if df_nodes.query('NODES == @i').iloc[0].NODE_DESC not in cl_node_description:
                l_aux.append(i)
            if df_nodes.query('NODES == @i').iloc[0].NODE_ORG not in cl_node_org_extended:
                l_aux.append(i)

    # cycle thru the list and remove these "unqualified" nodes from the set
    for i in l_aux:
        aux_set1.remove(i)

    # edges are complicated, as they may contain unwanted elements, either as SOURCE or TARGET
    df_edges_graph =df_edges[(df_edges.SOURCE.isin(aux_set1) | df_edges.TARGET.isin(aux_set1)) & df_edges.TYPE.isin(cl_node_type)]
    aux_set_source = {nodes for nodes in df_edges_graph.SOURCE}
    aux_set_target = {nodes for nodes in df_edges_graph.TARGET}
    # combinining the two sets, containing all nodes that were in the filtered df_edge_graph
    aux_set2 = aux_set_source | aux_set_target

    # create the difference between the two sets: result shows again potentially "undesirable" nodes
    aux_set3 = aux_set2 - aux_set1

    # finally, we must differentiate: nodes on the H-Level should be included (showing persons that other persons corresponding to 
    # the filter criterium are connected to. Those we do want to see - but not Projects or Competences that are not explicitly
    # mentioned in the filter criteria
    # Determining which nodes from aux_set3 are NOT Hierarchy elements:
    l_aux = []
    for i in aux_set3:
        if df_nodes.query('NODES == @i').empty:
            continue
        else:
            if df_nodes.query('NODES == @i').iloc[0].NODE_TYPE == 'H':
                l_aux.append(i)
    # cycle thru the list and remove these "unqualified" nodes from the set
    for i in l_aux:
        aux_set3.remove(i) 

    # using aux_set3 now to remove any row which contains the undesirable nodes, either as Source or as Target
    df_edges_graph = df_edges_graph[~df_edges_graph.SOURCE.isin(aux_set3)]
    df_edges_graph = df_edges_graph[~df_edges_graph.TARGET.isin(aux_set3)]

    # retrieving the nodes from the edge-info that must be extracted so that all edges can be shown with target and source
    df_edges_graph.reset_index(drop=True, inplace=True)
    aux_nodes_fin = set()
    for index in range(0,len(df_edges_graph)):
            aux_nodes_fin.add(df_edges_graph['SOURCE'][index])
            aux_nodes_fin.add(df_edges_graph['TARGET'][index])
    df_nodes_graph = df_nodes[(df_nodes.NODES.isin(aux_nodes_fin))].reset_index(drop=True)

    nodes = []
    for d in df_nodes_graph.to_dict(orient="records"):
        # if else in order to handle 'H'-nodes differently to display not only the node id, but also the node
        # description aka the department name !
        # tbc treatman of the org-information, e.g. as "parent node" to all nodes belonging to the same organisational unit
        if d.get("NODE_TYPE") == "H":
            nodes.append({'data': {'id': d.get("NODES"), 'label': d.get("NODES")+' (' + d.get("NODE_DESC")+')',
                                   'grabbable': True, 'type': d.get("NODE_TYPE"), 'description': d.get("NODE_DESC")}})
        else:
            nodes.append({'data': {'id': d.get("NODES"), 'label': d.get("NODES"),'grabbable': True, 'type': d.get("NODE_TYPE"), 'description': d.get("NODE_DESC")}})

    edges = []
    for d in df_edges_graph.to_dict(orient="records"):
        edges.append({'data': {'source': d.get("SOURCE"), 'target': d.get("TARGET"), 'weight':d.get("VALUE"),'type': d.get("TYPE")}})

    elements = nodes + edges
    
    return elements


# # 4) Actual Program
# ## 4a) Data Import

df_nodes = pd.read_csv(r'nodes.csv', sep=';')
df_edges = pd.read_csv(r'edges.csv', sep=';')

# ## 4b) Instantiate initial values for the graph settings

l_initial_node_type = ['H', 'C', 'P'] # 1st criterium list for node type
l_initial_node_desc = ['H_GA', 'H_GDPR_BRND', 'P_project1', 'C_skill5']
l_initial_org = df_nodes['NODE_ORG'].unique().tolist()
l_initial_org.remove('C')   # Competences must be removed from ORG list
l_initial_org.remove('P')   # Projects must be removed from ORG list
# C and P could cause confusion; they are added back in the filtering for the graph, as these nodes (and edges eminating from them)
# are independent from the ORG unit. Or, in other word: Projects and Competences are independent of any ORG units
#l_initial_org


# ## 4c) Building the dashboard layout

####################################################################################################################################################
app = dash.Dash(__name__, title = "CytONDA Organizational Network Discovery", external_stylesheets=[dbc.themes.LUX], suppress_callback_exceptions=True)
server = app.server
####################################################################################################################################################

l_stylesheet = [
        # Selector for all nodes
         {'selector': 'node',                     
            'style': {'content': 'data(label)'}}, 
        # conditional selector only for nodes with certain type value
          { 'selector': 'node[type="H"]',          
            'style': {'shape': 'square',
              'background-color': 'grey'}},
          { 'selector': 'node[type="P"]',
            'style': {'shape': 'circle',
              'background-color': 'blue'}},
          { 'selector': 'node[type="C"]',
            'style': {'shape': 'star',
              'background-color': 'green'}},
        # Selector for all edges
            {'selector': 'edge',
                'style': {'curve-style': 'bezier', 'width': 'data(weight)','target-arrow-shape': 'triangle-tee'}},
        # Conditional selector only for edges of certain type
            {'selector': 'edge[type="H"]', 
                'style': {'line-color': 'grey'}},
            {'selector': 'edge[type="P"]',
                'style': {'line-color': 'blue'}},
            {'selector': 'edge[type="C"]',
                'style': {'line-color': 'green'}}]

body = html.Div([
   html.H1("Visualization organisational knowledge network")
       
   , dbc.Row([dbc.Col(html.Div([dbc.Label("Displayed the following Node Types"),dbc.Checklist(options=[{"label": "Hierarchy", "value": "H" },
    {"label": "Projects", "value": "P"},{"label": "Competences", "value": "C"}], value=["H","P","C"], id="f_select_node_type", inline=True, switch=True,),]),width=4)
   , dbc.Col(html.Div([dbc.Label("Display the Nodes for the following organizational units: "),
                       dcc.Dropdown(options=[{'label': i, 'value': i} for i in l_initial_org], value = l_initial_org,
                                    id = 'f_select_org',multi=True)]), width=4)])

   , dbc.Row(dbc.Col(html.Div(dbc.Progress(value=100, color="info"))))  # Progress bar "perverted" to horizontal divider / ruler
       
   , dbc.Row(dbc.Col(html.Div([dbc.Label("Display the following Node Classes"),
                       dcc.Dropdown(options=[{'label': i, 'value': i} for i in l_initial_node_desc], placeholder = 'Select from the Node Classes (options depending on selected Node Type(s)', value = l_initial_node_desc,
                                    id = 'f_select_node_class',multi=True)])))    

   , dbc.Row(dbc.Col(html.Div(dbc.Progress(value=100, color="info"))))  # Progress bar "perverted" to horizontal divider / ruler
   ####################################################################################################################################### graph component
   , dbc.Row(dbc.Col(html.Div([cyto.Cytoscape(id='ONDA', layout={'name': 'breadthfirst'}, # breadfirst layout ensures almost hierachical layout !!!!
       style={'width': '100%', 'height': '650px'}, # before additional mousover data row: height = 800px
       elements=f_define_elements(df_nodes, df_edges, l_initial_node_desc, l_initial_org, l_initial_node_type),
       stylesheet = l_stylesheet)])))
   #######################################################################################################################################
   , dbc.Row([dbc.Col(html.H5('Click on node for details')), dbc.Col(html.H5('Click on edge for details'))])
   # additional row to display tap info for node and edge mousover -> see corresponding callback
   , dbc.Row([dbc.Col(html.Div(html.Pre(id='node_tap'))), dbc.Col(html.Div(html.Pre(id='edge_tap')))])
   ])


# ## 4d) define the callback functions for the interactive graph input components

# actually productive code: pushing the change in the network_type selection to trigger
# a corresponding change in the targets selection (only targets shown which have belong to the chosen network type(s)
@app.callback(
    dash.dependencies.Output(component_id='f_select_node_class', component_property='options'),        # component_property changed from "children"
    [dash.dependencies.Input(component_id='f_select_node_type', component_property='value')])
def update_node_classes(f_select_node_type):
    current_node_type = f_select_node_type
    df_aux = df_nodes[df_nodes.NODE_TYPE.isin(current_node_type)]
    return [{'label': i, 'value': i} for i in df_aux.NODE_DESC.unique()]

###################################callback for actual graph update
@app.callback(
    dash.dependencies.Output('ONDA', 'elements'),
    [dash.dependencies.Input('f_select_node_class', 'value'), dash.dependencies.Input('f_select_org', 'value')])

def update_output (f_class, f_org):
#    nodes_data = df_nodes
#    edges_data = df_edges
    cl_node_description = f_class
    cl_node_org = f_org
    ################## node-types to be displayed not dynamically updated from selector switch, but derived from the current node-class selection !
    aux_set2 = set()
    for node_class in cl_node_description:
        if df_nodes.query('NODE_DESC == @node_class').empty:
            continue
        else:
            aux_set2.add(df_nodes.query('NODE_DESC == @node_class').iloc[0].NODE_TYPE)
    cl_node_type = list(aux_set2)
    ##################
    return f_define_elements(df_nodes, df_edges, cl_node_description, cl_node_org, cl_node_type)


# callback to show tap info for node
@app.callback(dash.dependencies.Output('node_tap', 'children'),
              [dash.dependencies.Input('ONDA', 'tapNodeData')])
def displayTapNodeData(data):
    d_node_info_display_json = json.loads(json.dumps(data))
    l_node_info_display =[]
    try:
        for k, v in d_node_info_display_json.items():
            if k in l_node_attribs4display:
                l_node_info_display.append(k+": "+v+new_line)
    except:
        l_node_info_display = "No node clicked yet"
    return l_node_info_display

# callback to show tap info for edge
@app.callback(dash.dependencies.Output('edge_tap', 'children'),
              [dash.dependencies.Input('ONDA', 'tapEdgeData')])
def displayTapEdgeData(data):
    d_edge_info_display_json = json.loads(json.dumps(data))
    l_edge_info_display =[]
    if isinstance(d_edge_info_display_json, type(None)):
        l_edge_info_display = "No edge clicked yet"
    else:
        for k, v in d_edge_info_display_json.items():
            if k in l_edge_attribs4display:     # additional check as e.g. the weights are numeric and can thus not be just appended to string
                if type(v) != str:
                    l_edge_info_display.append(k+": "+str(v)+new_line)
                else:
                    l_edge_info_display.append(k+": "+v+new_line)
    return l_edge_info_display

# ## 4e) Run the dashboard
app.layout = html.Div([body])
if __name__ == "__main__":
	app.run_server(debug = True)

