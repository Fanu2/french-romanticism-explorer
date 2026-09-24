import sys, sqlite3, re
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QGuiApplication
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,
 QLabel,QLineEdit,QListWidget,QListWidgetItem,QTextBrowser,QPushButton,QSplitter,
 QMessageBox,QCheckBox,QComboBox)

DB=Path(__file__).with_name("JASS_French_Romanticism_Text.db")

class Explorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JASS French Romanticism — Text Explorer")
        self.resize(1450,850)
        self.conn=sqlite3.connect(DB)
        self.font_size=16
        self.dark=True
        self.results=[]
        self.build_ui()
        self.load_authors()
        self.apply_theme()

    def build_ui(self):
        root=QWidget(); self.setCentralWidget(root)
        main=QVBoxLayout(root)
        top=QHBoxLayout()
        title=QLabel("JASS French Romanticism")
        title.setObjectName("title")
        subtitle=QLabel("Full-text Poetry Explorer · Hugo · Lamartine · Musset · Vigny")
        self.search=QLineEdit(); self.search.setPlaceholderText("Search poems, collections or full text…")
        self.search.returnPressed.connect(self.do_search)
        btn=QPushButton("Search"); btn.clicked.connect(self.do_search)
        clear=QPushButton("Clear"); clear.clicked.connect(self.clear_search)
        self.theme=QPushButton("☀ Light"); self.theme.clicked.connect(self.toggle_theme)
        top.addWidget(title); top.addWidget(subtitle); top.addStretch(); top.addWidget(self.search,2); top.addWidget(btn); top.addWidget(clear); top.addWidget(self.theme)
        main.addLayout(top)

        split=QSplitter(Qt.Horizontal)
        left=QWidget(); ll=QVBoxLayout(left)
        ll.addWidget(QLabel("AUTHORS"))
        self.authors=QListWidget(); self.authors.currentItemChanged.connect(self.author_changed)
        ll.addWidget(self.authors)
        self.author_info=QLabel(); self.author_info.setWordWrap(True); ll.addWidget(self.author_info)
        split.addWidget(left)

        mid=QWidget(); ml=QVBoxLayout(mid)
        ml.addWidget(QLabel("POEMS"))
        self.poems=QListWidget(); self.poems.currentItemChanged.connect(self.poem_changed)
        ml.addWidget(self.poems)
        self.count=QLabel("0 poems"); ml.addWidget(self.count)
        split.addWidget(mid)

        right=QWidget(); rl=QVBoxLayout(right)
        self.poem_title=QLabel("Select a poem"); self.poem_title.setObjectName("poemTitle")
        self.meta=QLabel(""); self.meta.setWordWrap(True)
        rl.addWidget(self.poem_title); rl.addWidget(self.meta)
        self.reader=QTextBrowser(); self.reader.setOpenExternalLinks(True); rl.addWidget(self.reader,1)
        nav=QHBoxLayout()
        self.prev=QPushButton("← Previous"); self.prev.clicked.connect(self.prev_poem)
        self.next=QPushButton("Next →"); self.next.clicked.connect(self.next_poem)
        copy=QPushButton("Copy"); copy.clicked.connect(self.copy_text)
        minus=QPushButton("A−"); minus.clicked.connect(lambda:self.resize_font(-1))
        plus=QPushButton("A+"); plus.clicked.connect(lambda:self.resize_font(1))
        nav.addWidget(self.prev); nav.addWidget(self.next); nav.addStretch(); nav.addWidget(copy); nav.addWidget(minus); nav.addWidget(plus)
        rl.addLayout(nav)
        split.addWidget(right)
        split.setSizes([250,400,800])
        main.addWidget(split,1)

    def load_authors(self):
        self.authors.clear()
        for row in self.conn.execute("SELECT id,name,birth_year,death_year FROM authors ORDER BY name"):
            it=QListWidgetItem(row[1]); it.setData(Qt.UserRole,row)
            self.authors.addItem(it)
        if self.authors.count(): self.authors.setCurrentRow(0)

    def author_changed(self,cur,prev):
        if not cur:return
        aid,name,b,d=cur.data(Qt.UserRole)
        self.author_info.setText(f"<b>{name}</b><br>{b}–{d}<br>French Romanticism")
        self.search.clear()
        self.load_poems(aid)

    def load_poems(self,aid):
        self.results=[r for r in self.conn.execute("""SELECT p.id,p.title,COALESCE(p.collection,''),p.word_count
             FROM poems p JOIN works w ON p.work_id=w.id WHERE w.author_id=? ORDER BY COALESCE(p.title,'')""",(aid,))]
        self.refresh_poem_list()

    def refresh_poem_list(self):
        self.poems.blockSignals(True); self.poems.clear()
        for r in self.results:
            label=r[1] or "(untitled)"
            if r[2]: label += f"  ·  {r[2]}"
            it=QListWidgetItem(label); it.setData(Qt.UserRole,r); self.poems.addItem(it)
        self.poems.blockSignals(False)
        self.count.setText(f"{len(self.results)} poems")
        if self.poems.count(): self.poems.setCurrentRow(0)

    def poem_changed(self,cur,prev):
        if not cur:return
        pid,title,collection,wc=cur.data(Qt.UserRole)
        row=self.conn.execute("""SELECT a.name,w.title,p.title,p.collection,p.raw_text,p.poem_text,p.source_url,p.word_count
          FROM poems p JOIN works w ON p.work_id=w.id JOIN authors a ON w.author_id=a.id WHERE p.id=?""",(pid,)).fetchone()
        if not row:return
        author,work,title,collection,raw,poem,url,wc=row
        text=poem or raw
        self.poem_title.setText(title or "(untitled)")
        self.meta.setText(f"<b>{author}</b> · {work}" + (f" · {collection}" if collection else "") + f" · {wc or 0:,} words")
        self.reader.setPlainText(text)
        self.current_text=text
        self.current_url=url

    def do_search(self):
        q=self.search.text().strip()
        if not q:return
        try:
            rows=self.conn.execute("""SELECT p.id,p.title,COALESCE(p.collection,''),p.word_count,a.id,a.name
              FROM poems_fts f JOIN poems p ON p.id=f.rowid
              JOIN works w ON p.work_id=w.id JOIN authors a ON w.author_id=a.id
              WHERE poems_fts MATCH ? ORDER BY bm25(poems_fts) LIMIT 500""",(q,)).fetchall()
        except sqlite3.OperationalError:
            safe=re.sub(r'["*]',' ',q)
            rows=self.conn.execute("""SELECT p.id,p.title,COALESCE(p.collection,''),p.word_count,a.id,a.name
              FROM poems p JOIN works w ON p.work_id=w.id JOIN authors a ON w.author_id=a.id
              WHERE p.raw_text LIKE ? OR p.title LIKE ? LIMIT 500""",(f"%{safe}%",f"%{safe}%")).fetchall()
        self.results=rows
        self.refresh_search_list()

    def refresh_search_list(self):
        self.poems.blockSignals(True); self.poems.clear()
        for r in self.results:
            pid,title,col,wc,aid,author=r
            label=f"{title or '(untitled)'}  ·  {author}"
            if col: label += f" · {col}"
            it=QListWidgetItem(label); it.setData(Qt.UserRole,(pid,title,col,wc)); self.poems.addItem(it)
        self.poems.blockSignals(False)
        self.count.setText(f"{len(self.results)} search results")
        if self.poems.count(): self.poems.setCurrentRow(0)

    def clear_search(self):
        self.search.clear()
        cur=self.authors.currentItem()
        if cur:self.load_poems(cur.data(Qt.UserRole)[0])

    def prev_poem(self):
        r=self.poems.currentRow()
        if r>0:self.poems.setCurrentRow(r-1)

    def next_poem(self):
        r=self.poems.currentRow()
        if r+1<self.poems.count():self.poems.setCurrentRow(r+1)

    def copy_text(self):
        QGuiApplication.clipboard().setText(getattr(self,'current_text',''))

    def resize_font(self,d):
        self.font_size=max(10,min(30,self.font_size+d))
        f=self.reader.font(); f.setPointSize(self.font_size); self.reader.setFont(f)

    def toggle_theme(self):
        self.dark=not self.dark; self.apply_theme()
        self.theme.setText("☀ Light" if self.dark else "☾ Dark")

    def apply_theme(self):
        if self.dark:
            self.setStyleSheet("""QWidget{background:#111827;color:#e5e7eb} QLineEdit,QListWidget,QTextBrowser{background:#0b1220;color:#e5e7eb;border:1px solid #334155;border-radius:6px} QPushButton{background:#1f2937;color:#f8fafc;border:1px solid #475569;padding:7px 12px;border-radius:6px} QPushButton:hover{background:#334155} QLabel#title{font-size:24px;font-weight:700} QLabel#poemTitle{font-size:23px;font-weight:700}""")
        else:
            self.setStyleSheet("""QWidget{background:#f6f7f9;color:#202124} QLineEdit,QListWidget,QTextBrowser{background:white;color:#202124;border:1px solid #cbd5e1;border-radius:6px} QPushButton{background:white;color:#202124;border:1px solid #cbd5e1;padding:7px 12px;border-radius:6px} QLabel#title{font-size:24px;font-weight:700} QLabel#poemTitle{font-size:23px;font-weight:700}""")

    def closeEvent(self,e):
        self.conn.close(); e.accept()

if __name__=="__main__":
    app=QApplication(sys.argv)
    w=Explorer(); w.show()
    sys.exit(app.exec())
