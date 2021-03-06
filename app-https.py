import os
import tornado.ioloop
import tornado.web
import time
import wave_adpcm as wave
import numpy as np
import scipy.signal as signal
import json

MAX_STREAMED_SIZE = 1024 * 1024 * 1024

class otaUploadHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('''
        <html>
          <head><title>Upload File</title></head>
          <body>
            <form action='ota' enctype="multipart/form-data" method='post'>
            <input type='file' name='ota'/>
            <br/>
            <input type='submit' value='submit'/>
            </form>
          </body>
        </html>
        ''')

    def post(self):
        print("post")
        upload_path=os.path.join(os.path.dirname(__file__),'audio')
        file_metas=self.request.files['ota']    
        print(upload_path)
        print(file_metas)
        for meta in file_metas:
            filename=meta['filename']
            print(filename)
            filepath=os.path.join(upload_path,filename)
            with open(filepath,'wb') as up:      
                up.write(meta['body'])
            self.write('finished!')

@tornado.web.stream_request_body
class AudioUploadHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.save_name = ''
        self.save_size = 0
        self.last_time = time.time()

    def _new_wav(self, fmt, rates, bits, ch):
        t = time.localtime()
        tim = time.strftime('%Y%m%dT%H%M%SZ', t)
        filename = str.format('./audio/{}_{}_{}_{}.{}', tim, rates, bits, ch, fmt)
        if fmt == 'wav':
            f = wave.open(filename, 'wb')
            f.setparams((ch, int(bits/8), rates, 0, 'NONE', 'NONE'))
        else:
            f = open(filename, 'wb')
        self.last_time = time.time()
        self.save_size = 0
        return filename,f

    def _write_wav(self, filename, f, data):
        if filename.endswith('.wav') and f != None:
            f.writeframes(bytearray(data))
        else:
            f.write(bytearray(data))

    def _end_wav(self, f):
        if f != None:
            f.close()

    def prepare(self):
        self.request.connection.set_max_body_size(MAX_STREAMED_SIZE)
        try:
            headers = self.request.headers
            print(headers)
            
            sample_rates = headers.get('x-audio-sample-rates', '').lower()
            bits = headers.get('x-audio-bits', '').lower()
            channel = headers.get('x-audio-channel', '').lower()
            fmt = headers.get('x-audio-format', '').lower()
            print("Audio information, format: {}, sample rates: {}, bits: {}, channel(s): {}".format(fmt, sample_rates, bits, channel))
            
            if self.save_name == '':
                self.save_name, self.w_f = self._new_wav(fmt, int(sample_rates), int(bits), int(channel))
            print(self.save_name)
        except Exception:
            print('prepare error')

    def data_received(self,chunk):
        #print('data_received')
        
        if time.time() - self.last_time > 30:
            try:
                self._end_wav(self.w_f)
                self.save_name = ''
            except Exception:
                print('_end_wav error')
            try:
                headers = self.request.headers                
                sample_rates = headers.get('x-audio-sample-rates', '').lower()
                bits = headers.get('x-audio-bits', '').lower()
                channel = headers.get('x-audio-channel', '').lower()
                fmt = headers.get('x-audio-format', '').lower()
                print("Audio information, format: {}, sample rates: {}, bits: {}, channel(s): {}".format(fmt, sample_rates, bits, channel))
                
                if self.save_name == '':
                    self.save_name, self.w_f = self._new_wav(fmt, int(sample_rates), int(bits), int(channel))
                print(self.save_name)
            except Exception:
                print('prepare error')
        
        self.save_size += len(chunk)
        try:
            if self.save_name != '':
                self._write_wav(self.save_name, self.w_f, chunk)
        except Exception:
            print('_write_wav error')

    @tornado.gen.coroutine
    def post(self):
        print('receive:', self.save_size)
        try:
            self._end_wav(self.w_f)
            body = {'result':self.save_name, 'size':self.save_size}
            self.set_status(200)
            self.set_header('Content-type', 'application/json')
            self.write(json.dumps(body).encode())
            self.flush()
        except Exception:
            print('post error')
        finally:
            self.finish()

class FileReviewHandler(tornado.web.RequestHandler):
    def get(self):
        # ?????????????????????
        upload_path = os.path.join(os.path.dirname(__file__), 'audio')
        files = os.listdir(upload_path)
        for file in files:
            if os.path.isdir(file):
                files.remove(file)
        files.sort()
        self.render('files.html', files=files)
        
class FileDownloadHandler(tornado.web.RequestHandler):
    def get(self):
        filename = 'audio/'+self.get_argument('file')
        print('download:', filename)
        # ?????????????????????
        upload_path = os.path.join(os.path.dirname(__file__), 'files')
        file_path = os.path.join(upload_path, filename)

        #Content-Type??????????????????????????????????????????????????????????????????????????????
        self.set_header ('Content-Type', 'application/octet-stream')
        self.set_header ('Content-Disposition', 'attachment; filename='+filename)
        #???????????????????????????????????????????????????
        with open(filename, 'rb') as f:
            while True:
                data = f.read(1024)
                if not data:
                    break
                self.write(data)
        #?????????finish
        self.finish()

application = tornado.web.Application(
    handlers=[
              (r'/', FileReviewHandler),
              (r'/data', FileDownloadHandler),
              (r'/upload', AudioUploadHandler),
              (r'/ota', otaUploadHandler),
              ],    # ??????????????????
    template_path=os.path.join(os.path.dirname(__file__), "templates"), # ????????????
    static_path=os.path.join(os.path.dirname(__file__), "static"),  # ????????????????????????
    debug=True,
  )

if __name__ == "__main__":
    server = tornado.httpserver.HTTPServer(application
           , ssl_options={
           "certfile": os.path.join(os.path.abspath("."), "../tls_certificate/server/server.crt"),
           "keyfile": os.path.join(os.path.abspath("."), "../tls_certificate/server/server.key"),
           }
    )
    server.listen(8000)
    tornado.ioloop.IOLoop.instance().start()  # ??????
