import base64
import datetime
import io

import dash
from dash import Dash, html, dcc, Input, Output, State, dash_table
from dash.dash_table.Format import Group
import plotly.express as px

import pandas as pd


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets,
                suppress_callback_exceptions=True)

app.layout = html.Div([ # this code section taken from Dash docs https://dash.plotly.com/dash-core-components/upload
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files')
        ]),
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        # Allow multiple files to be uploaded
        multiple=True
    ),
    html.Div(id='output-div'),
    html.Div(id='output-datatable'),
])


def parse_contents(contents, filename, date):
    content_type, content_string = contents.split(',')

    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            # Assume that the user uploaded a CSV file
            df = pd.read_csv(
                io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename:
            # Assume that the user uploaded an excel file
            df = pd.read_excel(io.BytesIO(decoded))
            
        df['DPS'] = df.apply(lambda row: row.Damage / row.Duration, axis=1)
        df['CPS'] = df.apply(lambda row: row['Condition Cleanses'] / row.Duration, axis=1)
        df['RPS'] = df.apply(lambda row: row['Boon Strips'] / row.Duration, axis=1)
        df['HPS'] = df.apply(lambda row: row['Total Healing'] / row.Duration, axis=1)

    except Exception as e:
        print(e)
        return html.Div([
            'There was an error processing this file.'
        ])

    return html.Div([
        html.H5(filename),
        html.H6(datetime.datetime.fromtimestamp(date)),
        html.P("Select X axis data"),
        dcc.Dropdown(id='xaxis-data',
                     value='Fight Num',
                     options=[{'label':x, 'value':x} for x in df.columns]),
        html.P("Select Y axis data"),
        dcc.Dropdown(id='yaxis-data',
                     value = 'Duration DPS',
                     options=[{'label':x, 'value':x} for x in df.columns]),
        html.P("Select ColorBy"),
        dcc.Dropdown(id='color-data',
                     value = 'Profession',
                     options=[{'label':x, 'value':x} for x in df.columns]),
        html.P("Select SizeBy"),
        dcc.Dropdown(id='size-data',
                     value = 'Damage',
                     options=[{'label':x, 'value':x} for x in df.columns]),
        dcc.Checklist(id='tick',
                      options=[{'label': 'Enable linear x-axis ticks', 'value': 'linear'}],
                      value=['linear']),
        html.Button(id="submit-button", children="Create Graph"),
        html.Hr(),

        dash_table.DataTable(
            data=df.to_dict('records'),
            columns=[{'name': i, 'id': i} for i in df.columns],
            style_table={'height': '300px', 'maxheight': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
            page_size=15
        ),
        dcc.Store(id='stored-data', data=df.to_dict('records')),

        html.Hr(),  # horizontal line

        # For debugging, display the raw contents provided by the web browser
        html.Div('Raw Content'),
        html.Pre(contents[0:200] + '...', style={
            'whiteSpace': 'pre-wrap',
            'wordBreak': 'break-all'
        })
    ])


@app.callback(Output('output-datatable', 'children'),
              Input('upload-data', 'contents'),
              State('upload-data', 'filename'),
              State('upload-data', 'last_modified'))
def update_output(list_of_contents, list_of_names, list_of_dates):
    if list_of_contents is not None:
        children = [
            parse_contents(c, n, d) for c, n, d in
            zip(list_of_contents, list_of_names, list_of_dates)]
        return children


@app.callback(Output('output-div', 'children'),
              Input('submit-button','n_clicks'),
              State('stored-data','data'),
              State('xaxis-data','value'),
              State('yaxis-data', 'value'),
              State('color-data', 'value'),
              State('size-data', 'value'),
              Input("tick", "value"))

def make_graphs(n, data, x_data, y_data, c_data, s_data, tick_mode):
    if n is None:
        return dash.no_update
    else:
        scatter_fig = px.scatter(data, x=x_data, y=y_data, color=c_data, size=s_data, hover_data=['Name','Profession', 'Role'])
        

        if 'linear' in tick_mode:
            scatter_fig.update_layout(xaxis=dict(tickmode='linear', tick0=1, dtick=1))

        # print(data)
        return dcc.Graph(figure=scatter_fig)



if __name__ == '__main__':
    app.run_server(debug=True)