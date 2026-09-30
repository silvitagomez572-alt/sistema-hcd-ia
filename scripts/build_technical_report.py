"""Render the editable technical Markdown report to a real, paginated PDF."""
import html
import os
from pathlib import Path
import re
import subprocess
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Preformatted, KeepTogether

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'entrega/Informe_Tecnico_HCD_IA_Silvia_Gomez_Villagra.pdf'
SOURCE=OUT.with_suffix('.md')
FONT=Path(os.getenv('HCD_REPORT_FONT_DIR', '/usr/share/fonts/truetype/dejavu'))
for name,file in [('Body','DejaVuSans.ttf'),('Body-Bold','DejaVuSans-Bold.ttf'),('Mono','DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Body-Bold',italic='Body',boldItalic='Body-Bold')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='ReportBody',fontName='Body',fontSize=9,leading=13,spaceAfter=7,textColor=colors.HexColor('#203044')))
styles.add(ParagraphStyle(name='ReportTitle',fontName='Body-Bold',fontSize=30,leading=36,spaceBefore=22,spaceAfter=18,textColor=colors.HexColor('#12364b')))
styles.add(ParagraphStyle(name='Section',fontName='Body-Bold',fontSize=17,leading=22,spaceAfter=12,textColor=colors.HexColor('#126276')))
styles.add(ParagraphStyle(name='Subsection',fontName='Body-Bold',fontSize=11,leading=15,spaceBefore=9,spaceAfter=7,textColor=colors.HexColor('#12364b')))
styles.add(ParagraphStyle(name='Cell',fontName='Body',fontSize=7.7,leading=10.5,spaceAfter=0))
styles.add(ParagraphStyle(name='CodeBlock',fontName='Mono',fontSize=7.4,leading=10,backColor=colors.HexColor('#f0f4f6'),borderPadding=7,spaceBefore=5,spaceAfter=10))

def inline(text):
    text=html.escape(text)
    text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)
    text=re.sub(r'`([^`]+)`',r'<font name="Mono" size="8">\1</font>',text)
    return text

def footer(canvas,doc):
    canvas.saveState();w,h=doc.pagesize
    canvas.setStrokeColor(colors.HexColor('#126276'));canvas.setLineWidth(1.2);canvas.line(18*mm,h-14*mm,w-18*mm,h-14*mm)
    canvas.setFont('Body',7);canvas.setFillColor(colors.HexColor('#586979'))
    canvas.drawString(18*mm,h-11*mm,'HCD IA | INFORME TÉCNICO | 29/09/2026')
    canvas.drawString(18*mm,12*mm,'Entrega académica • Evidencia sintética • Procesamiento local')
    canvas.drawRightString(w-18*mm,12*mm,str(doc.page));canvas.restoreState()

def build():
    text=SOURCE.read_text()
    if '{{CODE_COMMIT}}' in text:
        text=text.replace('{{CODE_COMMIT}}',subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    if '{{CLEAN_RESULT}}' in text:
        import json
        p=ROOT/'entrega/validacion_instalacion_limpia.json'
        if p.exists():
            data=json.loads(p.read_text());ok=all(v==0 for v in data['checks'].values()) and len(data['checks'])==3
            clean='Instalación, pip check y pytest correctos' if ok else 'Bloqueada: '+str(data.get('blocked_at','sin resultado'))
        else:clean='Pendiente al generar este documento; no se afirma instalación limpia aprobada'
        text=text.replace('{{CLEAN_RESULT}}',clean)
    SOURCE.write_text(text)
    lines=text.splitlines();story=[];i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line=='---':story.append(PageBreak());i+=1;continue
        if line.startswith('```'):
            code=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):code.append(lines[i]);i+=1
            story.append(Preformatted('\n'.join(code),styles['CodeBlock'],maxLineLength=102));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+',c) for c in cells):rows.append([Paragraph(inline(c),styles['Cell']) for c in cells])
                i+=1
            count=len(rows[0]);width=174*mm
            widths=([width*.24,width*.76] if count==2 else [width/count]*count)
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#d7e9ed')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f6f8')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5.5),('BOTTOMPADDING',(0,0),(-1,-1),5.5),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#126276'))]))
            story.extend([table,Spacer(1,10)]);continue
        if line.startswith('# '):story.append(Paragraph(inline(line[2:]),styles['ReportTitle']));i+=1;continue
        if line.startswith('## '):story.append(Paragraph(inline(line[3:]),styles['Section']));i+=1;continue
        if line.startswith('### '):story.append(Paragraph(inline(line[4:]),styles['Subsection']));i+=1;continue
        paragraph=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```','---')):
            if lines[i].startswith('- ') or re.match(r'\d+\. ',lines[i]):break
            paragraph.append(lines[i].strip());i+=1
        value=' '.join(paragraph)
        if value.startswith('- '):value='• '+value[2:]
        story.append(Paragraph(inline(value),styles['ReportBody']))
    doc=SimpleDocTemplate(str(OUT),pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=18*mm,topMargin=23*mm,bottomMargin=22*mm,title='Sistema HCD IA — Informe técnico de entrega',author='Lic. en Química Silvia Andrea Gómez Villagra',subject='Validación técnica local con datos sintéticos, 29/09/2026')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(OUT)

if __name__=='__main__':build()
