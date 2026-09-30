"""Actual OCR on a generated synthetic image; no patient documents."""
import sys,json,io
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from PIL import Image,ImageDraw,ImageFont
from pipeline.ocr.modulo_ocr import procesar_imagen
im=Image.new('RGB',(1000,180),'white');font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',48)
ImageDraw.Draw(im).text((30,50),'PRUEBA SINTETICA 2026',font=font,fill='black')
b=io.BytesIO();im.save(b,format='PNG');result=procesar_imagen(b.getvalue())
assert 'PRUEBA' in result[0]['texto']
evidence={'actual_tesseract':True,'language':'spa','synthetic_image':True,'expected_word_detected':True,'patient_documents_used':False}
(root/'entrega/validacion_ocr.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence))
