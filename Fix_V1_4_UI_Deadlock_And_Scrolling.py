#!/usr/bin/env python3
"""Patch V1.4 UI deadlock, page scrolling, Activity Log scrolling, and Jump to Latest.

Usage:
 python Fix_V1_4_UI_Deadlock_And_Scrolling.py "C:\\path\\WPP_CMDB_IS_Gap_Analysis_V1_4.py"
"""
from __future__ import annotations
import ast, shutil, sys
from datetime import datetime
from pathlib import Path

SCROLLFRAME = r'''class ScrollFrame(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent)
        self.canvas=tk.Canvas(self,bg="#F4F6F8",highlightthickness=0)
        self.bar=ttk.Scrollbar(self,orient="vertical",command=self.canvas.yview)
        self.inner=ttk.Frame(self.canvas,padding=18)
        self.win=self.canvas.create_window((0,0),window=self.inner,anchor="nw")
        self.inner.bind("<Configure>",self._sync_region)
        self.canvas.bind("<Configure>",self._sync_width)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left",fill="both",expand=True)
        self.bar.pack(side="right",fill="y")
        self._bind_wheel(self.canvas)
        self._bind_wheel(self.inner)

    def _sync_region(self,event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_width(self,event):
        self.canvas.itemconfigure(self.win,width=event.width)

    def _bind_wheel(self,widget):
        widget.bind("<MouseWheel>",self._wheel,add="+")
        widget.bind("<Button-4>",self._wheel,add="+")
        widget.bind("<Button-5>",self._wheel,add="+")
        widget.bind("<Enter>",lambda e:self.canvas.focus_set(),add="+")

    def _wheel(self,event):
        if getattr(event,"num",None)==4:self.canvas.yview_scroll(-3,"units")
        elif getattr(event,"num",None)==5:self.canvas.yview_scroll(3,"units")
        elif getattr(event,"delta",0):self.canvas.yview_scroll(int(-event.delta/120)*3,"units")
        return "break"
'''

TEMPLATE = r'''    def _template_notice(self):
        """Main-thread-safe Bulk Load Template confirmation."""
        item=self.registry.get("bulk_load_template")
        if not item:return False
        loaded=datetime.fromisoformat(item["loaded_on"]).strftime("%d.%b.%Y").upper()
        return messagebox.askyesno(
            "Current Bulk Load Template",
            f"Current Load template was loaded on {loaded}.\n\n"
            "The bulk load will be created based on the loaded template. "
            "If the template has changed, upload the new template first.\n\n"
            f"Continue with {item['file_name']}?"
        )
'''

BULK = r'''    def bulk_click(self,source):
        domain="NW" if source=="network" else "Server"
        category="IS Network Category Report" if source=="network" else "IS Server Category Report"

        # First visible action: ask for the authoritative Load To IS input.
        load_path=filedialog.askopenfilename(
            title=f"Select {domain} Load To IS File",
            filetypes=FILE_TYPES
        )
        if not load_path:return
        self.say(f"{domain} Load To IS selected: {Path(load_path).name}")

        # All remaining UI dialogs run synchronously on the Tk main thread.
        if not self.require("IS Operating System Report","Bulk Load Template",category):return
        if not self._template_notice():return
        out=self.output_dir()
        if not out:return
        fmt="xlsx" if messagebox.askyesno("Output format","Create XLSX? Select No for CSV.") else "csv"

        # Only after every main-thread dialog completes do we start the worker.
        def task():
            name=f"{domain} OS Bulk Load"
            self.after(0,lambda:self.activity_start(name))
            cleanup_workdir(out);set_output_progress(self.progress)
            load_df=read_load_to_is_file(load_path,source,self.progress)
            state=category_decisions_from_load(source,load_df,self.paths[category],self.progress)
            paths=generate_bulk_load(
                load_df,source,self.paths["IS Operating System Report"],
                self.paths["Bulk Load Template"],out,fmt,
                lambda n:self.sync_yes("Missing FQDN",f"{n} devices do not have a valid FQDN. Generate .nw.wpp.net and include them?"),
                lambda n:True,self.progress,state
            )
            self.after(0,lambda:self.activity_complete(name,len(load_df),len(paths)))
            self.after(0,lambda outputs=list(paths):messagebox.showinfo(f"{domain} OS Bulk Load Complete","\n".join(outputs)))
        self.execute(task)
'''

LOGSCROLL = r'''    def _log_scroll(self,*args):
        self.log.yview(*args)
        self._log_auto_scroll=self.log.yview()[1]>=0.995
        self._update_jump_button()

    def _log_view_changed(self,first,last):
        self._log_auto_scroll=float(last)>=0.995
        self._update_jump_button()

    def _log_mousewheel(self,event):
        if getattr(event,"num",None)==4:self.log.yview_scroll(-3,"units")
        elif getattr(event,"num",None)==5:self.log.yview_scroll(3,"units")
        elif getattr(event,"delta",0):self.log.yview_scroll(int(-event.delta/120)*3,"units")
        self.after_idle(self._refresh_log_scroll_state)
        return "break"

    def _refresh_log_scroll_state(self):
        self._log_auto_scroll=self.log.yview()[1]>=0.995
        self._update_jump_button()

    def _update_jump_button(self):
        if hasattr(self,"jump_button"):
            self.jump_button.configure(state="disabled" if self._log_auto_scroll else "normal")

    def jump_to_latest(self):
        self.log.see("end")
        self.log.yview_moveto(1.0)
        self._log_auto_scroll=True
        self._update_jump_button()
        self.log.focus_set()
'''

def replace_top(source,name,repl):
    t=ast.parse(source);n=next(x for x in t.body if isinstance(x,(ast.FunctionDef,ast.ClassDef)) and x.name==name);L=source.splitlines(True);L[n.lineno-1:n.end_lineno]=[repl+'\n\n'];return ''.join(L)
def replace_method(source,name,repl):
    t=ast.parse(source);c=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=='App');n=next(x for x in c.body if isinstance(x,ast.FunctionDef) and x.name==name);L=source.splitlines(True);L[n.lineno-1:n.end_lineno]=[repl+'\n'];return ''.join(L)

def main():
    target=Path(sys.argv[1] if len(sys.argv)>1 else 'WPP_CMDB_IS_Gap_Analysis_V1_4.py').expanduser().resolve()
    if not target.is_file():print(f"ERROR: File not found: {target}",file=sys.stderr);return 2
    source=target.read_text(encoding='utf-8');ast.parse(source)
    source=replace_top(source,'ScrollFrame',SCROLLFRAME)
    source=replace_method(source,'_template_notice',TEMPLATE)
    source=replace_method(source,'bulk_click',BULK)
    for name in ['_log_scroll','_log_view_changed','_log_mousewheel','jump_to_latest']:
        # Replace from the consolidated block one method at a time after parsing definitions.
        tree=ast.parse(LOGSCROLL);node=next(n for n in tree.body[0].body if isinstance(n,ast.FunctionDef) and n.name==name) if False else None
    # Remove old log helper methods and insert the consolidated implementations before activity_start.
    t=ast.parse(source);c=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=='App');names={'_log_scroll','_log_view_changed','_log_mousewheel','_refresh_log_scroll_state','_update_jump_button','jump_to_latest'};L=source.splitlines(True)
    for n in sorted([x for x in c.body if isinstance(x,ast.FunctionDef) and x.name in names],key=lambda x:x.lineno,reverse=True):del L[n.lineno-1:n.end_lineno]
    source=''.join(L);anchor='    def activity_start(self,name):';source=source.replace(anchor,LOGSCROLL+'\n'+anchor,1)
    ast.parse(source);compile(source,str(target),'exec')
    backup=target.with_name(f"{target.stem}.backup_ui_fix_{datetime.now():%Y%m%d_%H%M%S}{target.suffix}");shutil.copy2(target,backup);target.write_text(source,encoding='utf-8')
    print(f"PATCHED: {target}");print(f"BACKUP : {backup}");print("FIXES  : Load To IS picker first + main-thread-safe template prompt + page/log scrolling + Jump to Latest");print("VALIDATION: AST and Python compilation passed");return 0
if __name__=='__main__':raise SystemExit(main())
