import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import threading
import os
import sys
import webbrowser

# RTL Arabic Text Fixes for Tkinter
import arabic_reshaper
from bidi.algorithm import get_display

def ar(text):
    """Reshape Arabic text to render properly RTL in Tkinter"""
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

# Import our custom modules
from utils import read_input_csv, generate_output_filename, haversine_distance
from decoder import run_decode_mode
from scraper import run_scrape_mode


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class GeoPlaceApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GeoPlaceID")
        self.geometry("1100x1000")
        self.resizable(False, False)
        
        # State variables
        self.filepath = None
        self.rows = []
        self.is_running = False
        self.cancel_flag = False
        
        self.setup_ui()

    def setup_ui(self):
        # Header Area
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.pack(pady=(20, 5), fill="x", padx=20)
        
        self.header = ctk.CTkLabel(self.frame_top, text=ar("🌍 GeoPlaceID"), font=("Tajawal", 32, "bold"))
        self.header.pack(side="top")
        
        # Docs Button
        self.btn_help = ctk.CTkButton(
            self.frame_top, text=ar("📖 شرح الاستخدام (دليل البرنامج)"), font=("Tajawal", 14), 
            fg_color="#3b82f6", hover_color="#2563eb", width=200, command=self.open_docs
        )
        self.btn_help.pack(side="top", pady=(10, 0))
        
        self.subheader = ctk.CTkLabel(self, text=ar("استخراج إحداثيات (خطوط الطول والعرض) من Place ID"), font=("Tajawal", 16))
        self.subheader.pack(pady=(5, 15))

        # --- Section 1: File Upload ---
        self.frame_file = ctk.CTkFrame(self)
        self.frame_file.pack(pady=10, padx=20, fill="x")
        
        self.lbl_file = ctk.CTkLabel(self.frame_file, text=ar("1. اختر ملف الإكسيل أو CSV:"), font=("Tajawal", 16, "bold"))
        self.lbl_file.pack(anchor="e", pady=(10, 5), padx=20)
        
        self.btn_browse = ctk.CTkButton(self.frame_file, text=ar("📁 اختيار الملف"), font=("Tajawal", 15), command=self.browse_file)
        self.btn_browse.pack(pady=10)
        
        self.lbl_file_info = ctk.CTkLabel(self.frame_file, text=ar("لم يتم اختيار ملف"), text_color="gray")
        self.lbl_file_info.pack(pady=(0, 10))

        # --- Section 2: Mode Selection ---
        self.frame_mode = ctk.CTkFrame(self)
        self.frame_mode.pack(pady=10, padx=20, fill="x")
        
        self.lbl_mode = ctk.CTkLabel(self.frame_mode, text=ar("2. اختر طريقة الاستخراج:"), font=("Tajawal", 16, "bold"))
        self.lbl_mode.pack(anchor="e", pady=(10, 5), padx=20)
        
        self.mode_var = tk.StringVar(value="decode")
        
        # Mode 1: Decode
        self.rb_decode = ctk.CTkRadioButton(
            self.frame_mode, text=ar("🔓 فك التشفير (سريع جداً - دقة تقريبية قد تختلف بضعة كيلومترات)"), 
            variable=self.mode_var, value="decode", font=("Tajawal", 14), command=self.toggle_compare_options
        )
        self.rb_decode.pack(anchor="e", pady=5, padx=30)
        
        # Mode 2: Scrape
        self.rb_scrape = ctk.CTkRadioButton(
            self.frame_mode, text=ar("🎯 فحص دقيق 100% (أبطأ - يحتاج إنترنت لمتصفح خفي)"), 
            variable=self.mode_var, value="scrape", font=("Tajawal", 14), command=self.toggle_compare_options
        )
        self.rb_scrape.pack(anchor="e", pady=5, padx=30)
        
        # Mode 3: Compare
        self.rb_compare = ctk.CTkRadioButton(
            self.frame_mode, text=ar("⚖️ مقارنة الطريقتين (للتجربة والاختبار)"), 
            variable=self.mode_var, value="compare", font=("Tajawal", 14), command=self.toggle_compare_options
        )
        self.rb_compare.pack(anchor="e", pady=5, padx=30)

        # Compare Options (Hidden by default)
        self.frame_compare_opts = ctk.CTkFrame(self.frame_mode, fg_color="transparent")
        
        self.lbl_compare = ctk.CTkLabel(self.frame_compare_opts, text=ar("عدد الصفوف للمقارنة:"))
        self.lbl_compare.pack(side="right", padx=10)
        
        self.entry_compare_count = ctk.CTkEntry(self.frame_compare_opts, width=60)
        self.entry_compare_count.insert(0, "20")
        self.entry_compare_count.pack(side="right")

        # --- Section 3: Execution ---
        self.frame_exec = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_exec.pack(pady=20, padx=20, fill="x")
        
        self.btn_start = ctk.CTkButton(self.frame_exec, text=ar("🚀 ابدأ الاستخراج"), font=("Tajawal", 18, "bold"), height=40, command=self.start_process)
        self.btn_start.pack(side="right", padx=10, expand=True, fill="x")
        
        self.btn_cancel = ctk.CTkButton(self.frame_exec, text=ar("🛑 إيقاف"), font=("Tajawal", 18), height=40, fg_color="#ef4444", hover_color="#dc2626", state="disabled", command=self.cancel_process)
        self.btn_cancel.pack(side="left", padx=10, expand=True, fill="x")

        # --- Section 4: Progress & Logs ---
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(pady=(0, 10), padx=20, fill="x")
        self.progress_bar.set(0)
        
        self.lbl_status = ctk.CTkLabel(self, text=ar("الجاهزية: في انتظار الملف"), font=("Tajawal", 14))
        self.lbl_status.pack(pady=(0, 5))
        
        self.log_box = ctk.CTkTextbox(self, height=150, font=("Consolas", 12))
        self.log_box.pack(pady=(0, 20), padx=20, fill="both", expand=True)

    def toggle_compare_options(self):
        if self.mode_var.get() == "compare":
            self.frame_compare_opts.pack(anchor="e", pady=5, padx=50)
        else:
            self.frame_compare_opts.pack_forget()

    def open_docs(self):
        """Open the HTML documentation file in default browser"""
        docs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "index.html")
        webbrowser.open(f"file://{docs_path}")

    def browse_file(self):
        filename = filedialog.askopenfilename(
            title=ar("اختر ملف CSV"),
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            try:
                self.rows = read_input_csv(filename)
                self.filepath = filename
                filename_only = os.path.basename(filename)
                self.lbl_file_info.configure(text=ar(f"📄 {filename_only} - ({len(self.rows)} صف)"), text_color="#10b981")
                self.log(ar(f"تم تحميل الملف بنجاح: {len(self.rows)} صف."))
            except Exception as e:
                messagebox.showerror(ar("خطأ في الملف"), str(e))
                self.lbl_file_info.configure(text=ar("❌ خطأ في قراءة الملف"), text_color="#ef4444")

    # Override log to auto-reshape incoming messages
    def log(self, message):
        self.log_box.insert(tk.END, ar(message) + "\n")
        self.log_box.see(tk.END)
        self.update()

    def update_progress(self, current, total, message, is_error=False):
        if total > 0:
            self.progress_bar.set(current / total)
        self.lbl_status.configure(text=ar(message))
        self.log(message)  # The log method itself calls ar()

    def is_cancelled(self):
        return self.cancel_flag

    def cancel_process(self):
        if self.is_running:
            self.cancel_flag = True
            self.lbl_status.configure(text=ar("جاري الإيقاف..."))
            self.btn_cancel.configure(state="disabled")

    def start_process(self):
        if not self.filepath or not self.rows:
            messagebox.showwarning(ar("تنبيه"), ar("الرجاء اختيار ملف أولاً"))
            return
            
        self.is_running = True
        self.cancel_flag = False
        self.btn_start.configure(state="disabled")
        self.btn_browse.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progress_bar.set(0)
        self.log_box.delete("1.0", tk.END)
        
        mode = self.mode_var.get()
        base_dir = os.path.dirname(self.filepath)
        
        # Run in thread to not freeze GUI
        thread = threading.Thread(target=self._run_thread, args=(mode, base_dir))
        thread.daemon = True
        thread.start()

    def _run_thread(self, mode, base_dir):
        try:
            if mode == "decode":
                out_path = generate_output_filename(base_dir, "decoded")
                self.log("🚀 بدء عملية فك التشفير السريعة (بدون إنترنت)...")
                run_decode_mode(self.rows, out_path, self.update_progress, self.is_cancelled)
                
            elif mode == "scrape":
                out_path = generate_output_filename(base_dir, "scraped_exact")
                self.log("🚀 بدء الفحص الدقيق 100% (قد يستغرق وقتاً طويلاً)...")
                self.log("💡 سيتم حفظ التقدم تلقائياً للعودة في أي وقت.")
                run_scrape_mode(self.rows, out_path, self.update_progress, self.is_cancelled)
                
            elif mode == "compare":
                count = int(self.entry_compare_count.get())
                out_path = generate_output_filename(base_dir, f"comparison_{count}")
                self.log(f"🚀 بدء مقارنة الطريقتين على أول {count} صف...")
                self._run_compare(count, out_path)
                
        except Exception as e:
            self.update_progress(0, 1, f"❌ حدث خطأ غير متوقع: {str(e)}", True)
            
        finally:
            self.is_running = False
            self.btn_start.configure(state="normal")
            self.btn_browse.configure(state="normal")
            self.btn_cancel.configure(state="disabled")

    def _run_compare(self, count, out_path):
        from decoder import decode_place_id
        from scraper import extract_coords_from_url, ensure_browser
        import time
        from playwright.sync_api import sync_playwright
        import csv
        
        rows_to_process = self.rows[:count]
        total = len(rows_to_process)
        results = []
        
        if not ensure_browser(self.update_progress):
            return
            
        self.update_progress(0, total, "⏳ جاري تشغيل أداة المقارنة...", False)
            
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context()
            page = ctx.new_page()
            
            for i, row in enumerate(rows_to_process):
                if self.is_cancelled():
                    break
                    
                pid = row.get("Place_ID", "")
                name = row.get("Place_Name", "")
                
                # 1. Decode
                dec_lat, dec_lng = decode_place_id(pid)
                
                # 2. Scrape
                scr_lat, scr_lng = None, None
                try:
                    place_url = f"https://www.google.com/maps/place/?q=place_id:{pid}"
                    page.goto(place_url, wait_until="commit", timeout=15000)
                    for _ in range(12):
                        time.sleep(1)
                        if self.is_cancelled(): break
                        try:
                            real_url = page.evaluate("() => window.location.href")
                            scr_lat, scr_lng = extract_coords_from_url(real_url)
                            if scr_lat: break
                        except Exception: pass
                except Exception:
                    pass
                    
                # Calculate diff
                diff_m = haversine_distance(dec_lat, dec_lng, scr_lat, scr_lng)
                
                results.append({
                    "Name": name,
                    "Place_ID": pid,
                    "Decoded_Lat": dec_lat, "Decoded_Lng": dec_lng,
                    "Scraped_Lat": scr_lat, "Scraped_Lng": scr_lng,
                    "Diff_Meters": round(diff_m, 1) if diff_m else ""
                })
                
                msg = f"مقارنة {name[:20]}: فك التشفير({dec_lat}), الفحص({scr_lat}) -> فرق {round(diff_m,1) if diff_m else '?'} م"
                self.update_progress(i + 1, total, msg, False)
                
            browser.close()
            
        # Write
        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Name", "Place_ID", "Decoded_Lat", "Decoded_Lng", "Scraped_Lat", "Scraped_Lng", "Diff_Meters"])
            writer.writeheader()
            writer.writerows(results)
            
        if not self.is_cancelled():
            self.update_progress(total, total, f"🎉 اكتملت المقارنة! تم الحفظ: {out_path}", False)


if __name__ == "__main__":
    app = GeoPlaceApp()
    app.mainloop()
