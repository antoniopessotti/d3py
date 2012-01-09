import pandas
import json
from css import CSS

import webbrowser
from HTTPHandler import CustomHTTPRequestHandler, ThreadedHTTPServer
import threading

import os
import tempfile
import shutil

class D3object(object):
    def add_js(self,s):
        """
        adds a line of javascript to the js object. Tries to do
        some nice formatting
        """
        if not (s.startswith("function") or s.startswith("}")):
            self.js += "\t"
        if s.startswith('.'):
            self.js += "\t"
        self.js += s
        self.js += "\n"
        if s.endswith(";"):
            self.js += "\n"

    def build_js():
        raise NotImplementedError
    def build_css():
        raise NotImplementedError
    def build_html():
        raise NotImplementedError
    def build_geoms():
        raise NotImplementedError

    def save_data(self, where=None):
        raise NotImplementedError
    def save_css(self, where=None):
        raise NotImplementedError
    def save_js(self, where=None):
        raise NotImplementedError
    def save_html(self, where=None):
        raise NotImplementedError

    def build(self):
        self.build_js()
        self.build_css()
        self.build_html()
        self.build_geoms()

    def update(self, where=None):
        self.build()
        self.save(where)

    def save(self, where=None):
        if where is not None and not os.path.isdir(where):
            try:
                os.makedirs(where)
            except Exception, e:
                print "Could not create directory structure %s: %s"%(where,e)
        self.save_data(where)
        self.save_css(where)
        self.save_js(where)
        self.save_html(where)

    def show(self):
        self.update()
        self.save()
    

class Figure(D3object):
    def __init__(self, data, name, width=400, height=100, margin=10, port=8000, template=None, **kwargs):
        """
        data : dataFrame
            data used for the plot. This dataFrame is column centric
        name : string
            name of visualisation. This will appear in the title
            bar of the webpage, and is the name of the folder where
            your files will be stored.
        """
        # store data
        self.name = name
        self.data = data
        self.work_dir = tempfile.mkdtemp(prefix="d3py-%s"%self.name)
        self.save_data()
        # Networking stuff
        self.port          = port
        self.server_thread = None
        self.httpd         = None
        # initialise strings
        self.js        = ""
        self.css       = CSS()
        self.html      = ""
        self.template  = template or 'static/d3py_template.html'
        self.js_geoms  = ""
        self.css_geoms = CSS()
        self.geoms     = []
        # misc arguments
        self.args = {"width" : width, "height" : height, "margin" : margin}
        self.args.update(kwargs)

    def set_data(self, data):
        errmsg = "the %s geom requests %s which is not the given dataFrame!"
        for geom in self.geoms:
            for param in geom.params:
                if param:
                    assert p in data, errmsg%(geom.name, param)
        self.update()
        
    def add_geom(self, geom):
        errmsg = "the %s geom requests %s which is not in our dataFrame!"
        for p in geom.params:
            if p:
                assert p in self.data, errmsg%(geom.name, p)
        self.geoms.append(geom)
        self.save()

    def build_js(self):
        self.js = ""
        self.add_js("function draw(data){")
        self.add_js("g = d3.select('#chart')")
        self.add_js(".append('svg:svg')")
        self.add_js(".append('svg:g');")
        self.add_js("var scales = {")
        width, height, margin = self.args["width"], self.args["height"], self.args["margin"]
        for colname in self.data.columns:
            self.add_js("\t%s_y: d3.scale.linear()"%  colname                                          )
            self.add_js(".domain([%s, %s])"        % (max(self.data[colname]), min(self.data[colname])))
            self.add_js(".range([%s, %s]),"        % (margin, height-margin)                           )
            self.add_js("\t%s_x: d3.scale.linear()"%  colname                                          )
            self.add_js(".domain([%s, %s])"        % (min(self.data[colname]), max(self.data[colname])))
            self.add_js(".range([%s, %s]),"        % (margin, width-margin)                            )
        self.add_js("\t};")

    def build_css(self):
        # build up the basic css
        chart = {"border" : "1px solid", "border-radius": "5px", "box-shadow": "10px 10px 5px #888888"}
        chart.update(self.args)
        self.css["#chart"] = chart

    def build_html(self):
        # we start the html using a template - it's pretty simple
        self.html = open(self.template).read()
        self.html = self.html.replace("{{ port }}", str(self.port))
        self.html = self.html.replace("{{ name }}", self.name)
        self.save_html()

    def build_geoms(self):
        self.js_geoms = ""
        self.css_geoms = CSS()
        for geom in self.geoms:
            geom.build_js()
            geom.build_css()
            self.js_geoms += str(geom.js)
            self.css_geoms += geom.css

    def __add__(self, geom):
        self.add_geom(geom)
    
    def __iadd__(self, geom):
        self.add_geom(geom)
        return self
    
    def data_to_json(self):
        d = [ 
            dict([
                (colname, row[i]) 
                for i,colname in enumerate(self.data.columns)
            ])
            for row in self.data.values
        ]
        return json.dumps(d)

    def save_data(self,where=None):
        # write data
        fh = open("%s/%s.json"%(where or self.work_dir, self.name), 'w+')
        fh.write(self.data_to_json())
        fh.close()

    def save_css(self, where=None):
        # write css
        fh = open("%s/%s.css"%(where or self.work_dir, self.name), 'w+')
        fh.write("%s\n%s"%(self.css, self.css_geoms))
        fh.close()

    def save_js(self, where=None):
        # write javascript
        fh = open("%s/%s.js"%(where or self.work_dir, self.name), 'w+')
        fh.write(self.js + "\n" + self.js_geoms + "}")
        fh.close()

    def save_html(self, where=None):
        # write html
        fh = open("%s/%s.html"%(where or self.work_dir,self.name),'w+')
        fh.write(self.html)
        fh.close()

    def show(self):
        super(Figure, self).show()
        self.serve()
        # fire up a browser 
        webbrowser.open_new_tab("http://localhost:%s/%s.html"%(self.port, self.name))

    def serve(self):
        """
        start up a server to serve the files for this vis. 
            
        """
        if self.server_thread is None or self.server_thread.active_count() == 0:
            Handler = CustomHTTPRequestHandler
            Handler.directory = self.work_dir
            #httpd = SocketServer.TCPServer(("", PORT), Handler)
            port = self.port
            started = False
            while port < self.port + 50:
                try:
                    self.httpd = ThreadedHTTPServer(("", port), Handler)
                    started = True
                    break
                except Exception, e:
                    print "Exception %s: trying port %d"%(e,port)
                    port += 1
            if started is True:
                self.port = port
                self.server_thread = threading.Thread(target=self.httpd.serve_forever)
                self.server_thread.daemon = True
                self.server_thread.start()
                print "you can find your chart at http://localhost:%s/%s/%s.html"%(self.port, self.name, self.name)
            else:
                print "Could not open httpd server!"

    def __del__(self):
        try:
            if self.httpd is not None:
                print "Shutting down httpd"
                self.httpd.shutdown()
                self.httpd.server_close()
            try:
                print "Cleaning temp files"
                shutil.rmtree(self.work_dir)
            except:
                pass
        except Exception, e:
            print "Error in clean-up: %s"%e

if __name__ == "__main__":
    import numpy as np
    from geoms import *
    
    # some test data
    T = 10
    df = pandas.DataFrame({
        "time" : range(T),
        "pressure": np.random.rand(T),
        "temp" : np.random.rand(T)
    })
    # draw, psuedo ggplot style
    fig = Figure(df, name="random_temp", width=300, height=300) # instantiates the figure object
    #fig += Line(x="time", y="temp", stroke="red") # adds a red line
    fig += Point(x="pressure", y="temp", fill="red") # adds red points

    fig1 = Figure(df, name="random_temp") # instantiates the figure object
    fig1 += Bar(x="time", y="temp")
    fig1.show() # writes 3 files, then draws some beautiful thing in Chrome
