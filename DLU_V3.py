"""
DLU - V3.0

Description: Un outil de recherche de données dans des fichiers avec une interface graphique incroyable.
Auteur: [Saucisson.flp]
Date: 28/06/2025
"""
import os
import sys
import json
import csv
import tkinter as tk # Ajout de colorchooser
from tkinter import ttk, filedialog, scrolledtext, font as tkFont, colorchooser
from concurrent.futures import ProcessPoolExecutor, as_completed
import queue 
import multiprocessing # Pour freeze_support avec ProcessPoolExecutor
import platform

# Glisser-Déposer
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    TkinterDnD = None # Garder une trace si l'import échoue

# Importation conditionnelle de ctypes pour les coins arrondis sur Windows uniquement /!\
_ctypes_available = False
if platform.system() == "Windows":
    try:
        import ctypes
        from ctypes import wintypes
        _ctypes_available = True
    except ImportError:
        print("ctypes non disponible, les coins arrondis de la fenêtre ne seront pas appliqués.")
        _ctypes_available = False

class RechercheDBAppTk:
    CONFIG_FILE_PATH = "config.json"

    def __init__(self, master):
        self.master = master
        master.overrideredirect(True) 
        master.title('DLU - V3.0 [BETA]')
        master.attributes('-alpha', 0.0)

        # Définition des couleurs
        self.COLOR_BG_PRIMARY = '#0d1b2a'
        self.COLOR_TITLE_BAR_BG = '#0A111F' # Légèrement plus foncée que BG_PRIMARY
        self.COLOR_BG_SECONDARY = '#1b263b' # Utilisée pour TEntry, TProgressbar trough
        self.COLOR_ACCENT = '#415a77' # Utilisée pour TButton, TProgressbar bar
        self.COLOR_TEXT_PRIMARY = '#e0e1dd' # Couleur de texte principale
        self.COLOR_TITLE_BAR_BORDER = self.COLOR_BG_SECONDARY # Couleur pour la ligne de séparation sous la barre de titre
        self.COLOR_TEXT_ACCENT = '#778da9' # Utilisé pour le bouton "Rechercher"
        self.TRANSPARENT_COLOR = 'lime green' # Couleur qui sera rendue transparente pour les coins
        self.PLACEHOLDER_TEXT_DB_INPUT = "Entrez la db à rechercher"

        # Configuration de la transparence pour les coins arrondis (Windows)
        if _ctypes_available and platform.system() == "Windows":
            master.attributes("-transparentcolor", self.TRANSPARENT_COLOR)
            master.configure(bg=self.TRANSPARENT_COLOR) # Le fond de master doit être cette couleur
        # else:
            # Sur d'autres OS, ou si ctypes n'est pas dispo, le root_container avec son propre BG
            # remplira la fenêtre. Pas besoin de configurer master.bg car root_container le couvrira.

        self.dossier_parent = ''
        self.ui_queue = queue.Queue() 


        self.search_hits_count = 0
        self.search_errors_count = 0
        self.search_duplicates_count = 0 

        self._placeholder_disappear_job_id = None
        self._placeholder_appear_job_id = None
        self._is_placeholder_animating = False

        default_font_details = tkFont.nametofont("TkDefaultFont").actual()
        self.DEFAULT_FONT_FAMILY = default_font_details['family']
        # Utiliser une taille de police par défaut positive et raisonnable
        self.DEFAULT_FONT_SIZE = default_font_details.get('size', 9)
        if self.DEFAULT_FONT_SIZE < 0: # Les tailles négatives sont en pixels, convertir en points approx.
            self.DEFAULT_FONT_SIZE = 9 # Ou une autre valeur par défaut jugée appropriée

        # Définition des thèmes
        self.themes = {
            "Spécial H3xorrr": {
                "BG_PRIMARY": '#0d1b2a', "TITLE_BAR_BG": '#0A111F', "BG_SECONDARY": '#1b263b',
                "ACCENT": '#415a77', "TEXT_PRIMARY": '#e0e1dd', "TITLE_BAR_BORDER": '#1b263b',
                "TEXT_ACCENT": '#778da9',
                "COLOR_RESULT_NEW": "#33FF57", "COLOR_RESULT_ERROR": "#FF0000",
                "FONT_FAMILY_RESULTS": self.DEFAULT_FONT_FAMILY, "FONT_SIZE_RESULTS": self.DEFAULT_FONT_SIZE
            },
            "Sombre (Noir/Gris/Blanc)": {
                "BG_PRIMARY": '#1e1e1e', "TITLE_BAR_BG": '#141414', "BG_SECONDARY": '#2c2c2c',
                "ACCENT": '#5a5a5a', "TEXT_PRIMARY": '#f0f0f0', "TITLE_BAR_BORDER": '#3c3c3c',
                "TEXT_ACCENT": '#a0a0a0',
                "COLOR_RESULT_NEW": "#00FF00", "COLOR_RESULT_ERROR": "#FF4444",
                "FONT_FAMILY_RESULTS": self.DEFAULT_FONT_FAMILY, "FONT_SIZE_RESULTS": self.DEFAULT_FONT_SIZE
            },
            "Clair": {
                "BG_PRIMARY": '#f0f0f0', "TITLE_BAR_BG": '#e0e0e0', "BG_SECONDARY": '#ffffff',
                "ACCENT": '#0078d4', "TEXT_PRIMARY": '#1e1e1e', "TITLE_BAR_BORDER": '#cccccc',
                "TEXT_ACCENT": '#505050',
                "COLOR_RESULT_NEW": "#00AA00", "COLOR_RESULT_ERROR": "#EE0000",
                "FONT_FAMILY_RESULTS": self.DEFAULT_FONT_FAMILY, "FONT_SIZE_RESULTS": self.DEFAULT_FONT_SIZE
            }
        }
        self.current_theme_name = "Spécial H3xorrr" # Thème par défaut
        self._load_theme_settings(self.current_theme_name) # Charge tous les paramètres du thème

        # Charger les paramètres depuis le fichier AVANT d'initialiser les Var de Tkinter
        self._load_app_settings() 

        # Paramètres de recherche d'extensions
        self.DEFAULT_EXTENSIONS_LIST = ['.txt', '.sql', '.csv']
        self.current_extensions_list = list(self.DEFAULT_EXTENSIONS_LIST)
        self.extensions_str_var = tk.StringVar(value=",".join(self.DEFAULT_EXTENSIONS_LIST))
        self.filter_duplicates_var = tk.BooleanVar(value=True) 
        self.filter_duplicates_enabled = True 
        self.DEFAULT_MAX_WORKERS = min(max(1, (os.cpu_count() or 1) // 2), 32) # Défaut plus conservateur
        self.current_max_workers = self.DEFAULT_MAX_WORKERS
        self.max_workers_var = tk.IntVar(value=self.current_max_workers)
        self.case_sensitive_var = tk.BooleanVar(value=False) # Par défaut, insensible à la casse
        # Paramètres d'exclusion
        self.DEFAULT_EXCLUDED_PATHS_LIST = [".git", ".svn", "node_modules", "__pycache__", "venv", ".venv", "target", "build", "dist"]
        self.current_excluded_paths_list = list(self.DEFAULT_EXCLUDED_PATHS_LIST)
        self.excluded_paths_str_var = tk.StringVar(value=",".join(self.current_excluded_paths_list))

        self.selected_theme_var = tk.StringVar(value=self.current_theme_name)

        # Variables pour l'onglet Affichage (initialisées après le chargement du premier thème)
        self.selected_font_family_var = tk.StringVar(value=self.FONT_FAMILY_RESULTS)
        self.selected_font_size_var = tk.IntVar(value=self.FONT_SIZE_RESULTS)
        self.new_item_color_var = tk.StringVar(value=self.COLOR_RESULT_NEW)
        self.error_item_color_var = tk.StringVar(value=self.COLOR_RESULT_ERROR)

        self._init_ui()
        self._apply_styles() # Doit être appelé APRÈS _init_ui où title_bar est créé
        # Variables pour le déplacement de la fenêtre
        self._offset_x = 0
        self._offset_y = 0
        self.master.after(100, self._process_ui_queue) # Vérifier la file d'attente de l'UI régulièrement

        # Appliquer les coins arrondis pour la fenêtre principale (Windows uniquement)
        if _ctypes_available:
            self.master.after(50, lambda: self._apply_rounded_corners_windows(radius=20)) # Premier appel
            self.master.bind("<Configure>", lambda event: self._on_window_configure_for_rounding(event, radius=20))

        # Centrer la fenêtre avant de la rendre visible
        self._center_window()

        # Configurer le Glisser-Déposer si tkinterdnd2 est disponible
        if TkinterDnD:
            self.root_container.drop_target_register(DND_FILES)
            self.root_container.dnd_bind('<<Drop>>', self._handle_dnd_folder_drop)

        # Gérer la sauvegarde des paramètres à la fermeture
        self.master.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Démarrer l'animation de fondu enchaîné
        self._animate_fade_in()

    def _load_theme_settings(self, theme_name):
        """Charge tous les paramètres du thème spécifié."""
        theme = self.themes[theme_name]
        self.COLOR_BG_PRIMARY = theme["BG_PRIMARY"]
        self.COLOR_TITLE_BAR_BG = theme["TITLE_BAR_BG"]
        self.COLOR_BG_SECONDARY = theme["BG_SECONDARY"]
        self.COLOR_ACCENT = theme["ACCENT"]
        self.COLOR_TEXT_PRIMARY = theme["TEXT_PRIMARY"]
        self.COLOR_TITLE_BAR_BORDER = theme["TITLE_BAR_BORDER"]
        self.COLOR_TEXT_ACCENT = theme["TEXT_ACCENT"]
        self.COLOR_RESULT_NEW = theme["COLOR_RESULT_NEW"]
        self.COLOR_RESULT_ERROR = theme["COLOR_RESULT_ERROR"]
        self.FONT_FAMILY_RESULTS = theme["FONT_FAMILY_RESULTS"]
        self.FONT_SIZE_RESULTS = theme["FONT_SIZE_RESULTS"]

    def _center_window(self):
        self.master.update_idletasks() # S'assurer que les dimensions de la fenêtre sont à jour
        width = self.master.winfo_width()
        height = self.master.winfo_height()
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.master.geometry(f'{width}x{height}+{x}+{y}')

    def _init_ui(self):
        # Conteneur racine qui aura la couleur de fond principale
        # et permettra de placer la barre de titre personnalisée au-dessus du contenu
        self.root_container = tk.Frame(self.master, bg=self.COLOR_BG_PRIMARY) # Fait de root_container un attribut
        self.root_container.pack(fill=tk.BOTH, expand=True)

        # --- Barre de titre personnalisée ---
        self.title_bar = tk.Frame(self.root_container, bg=self.COLOR_TITLE_BAR_BG, relief=tk.FLAT, bd=0)
        self.title_bar.pack(fill=tk.X)

        title_text = self.master.title()
        self.title_label = tk.Label(self.title_bar, text=title_text, bg=self.COLOR_TITLE_BAR_BG, fg=self.COLOR_TEXT_PRIMARY, padx=10, pady=5, anchor='w')
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.close_button = tk.Button(self.title_bar, text='✕', command=self.master.destroy, # Fait un attribut
                                 bg=self.COLOR_TITLE_BAR_BG, fg=self.COLOR_TEXT_PRIMARY,
                                 activebackground='red', activeforeground='white', relief=tk.FLAT, bd=0, padx=10, pady=5, font=("Arial", 10, "bold"))
        self.close_button.pack(side=tk.RIGHT)

        self.settings_button = tk.Button(self.title_bar, text='\u2699', command=self._toggle_view, # ⚙️ Gear icon
                                 bg=self.COLOR_TITLE_BAR_BG, fg=self.COLOR_TEXT_PRIMARY,
                                 activebackground=self.COLOR_ACCENT, activeforeground=self.COLOR_TEXT_PRIMARY,
                                 relief=tk.FLAT, bd=0, padx=8, pady=5, font=("Arial", 12))
        self.settings_button.pack(side=tk.RIGHT, padx=(0,5))
        
        # Ligne de séparation sous la barre de titre pour mieux la discerner
        self.separator_line = tk.Frame(self.root_container, height=1, bg=self.COLOR_TITLE_BAR_BORDER) # Fait un attribut
        self.separator_line.pack(fill=tk.X)

        # --- Cadre principal pour le contenu de l'application ---
        # main_frame = ttk.Frame(self.root_container, padding="10") # Ce cadre n'est plus nécessaire ici
        # # main_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1) # Ce pack sera géré par _build_main_view

        # --- Cadre hôte pour basculer les vues ---
        self.content_host_frame = ttk.Frame(self.root_container)
        self.content_host_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._build_main_view()
        self._build_settings_view()

        self.current_view_frame = self.main_view_frame # La vue actuelle
        self.main_view_frame.pack(fill=tk.BOTH, expand=True) # Afficher la vue principale au démarrage
        self.settings_view_frame.pack_forget() # S'assurer que la vue des paramètres est cachée

    def _build_main_view(self):
        """Construit l'interface utilisateur principale de l'application."""
        self.main_view_frame = ttk.Frame(self.content_host_frame, padding="10")
        
        # --- Input Frame ---
        input_frame = ttk.Frame(self.main_view_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        # input_frame.configure(style='Custom.TFrame')

        ttk.Label(input_frame, text="Data:").pack(side=tk.LEFT, padx=(0, 10))

        self.batabase_input = ttk.Entry(input_frame, width=40) # Style sera appliqué par _on_db_input_focus_out
        self.batabase_input.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.batabase_input.insert(0, self.PLACEHOLDER_TEXT_DB_INPUT)
        self.batabase_input.bind("<FocusIn>", self._on_db_input_focus_in)
        self.batabase_input.bind("<FocusOut>", self._on_db_input_focus_out)
        self.batabase_input.bind("<KeyRelease>", self._on_db_input_keyrelease) # Pour interrompre l'animation si l'utilisateur tape
        # Appliquer le style placeholder initialement, sans animation pour le premier affichage
        self.batabase_input.configure(style='Placeholder.TEntry')

        self.dossier_button = ttk.Button(input_frame, text="Choisir Dossier", command=self.choisir_dossier)
        self.dossier_button.pack(side=tk.LEFT, padx=(0, 5))

        self.rechercher_button = ttk.Button(input_frame, text="Rechercher", style="Accent.TButton", command=self.lancer_recherche)
        self.rechercher_button.pack(side=tk.LEFT)

        # --- Results Text Area ---
        self.resultats_text = scrolledtext.ScrolledText(self.main_view_frame, wrap=tk.WORD, height=15, state='disabled',
                                                       background=self.COLOR_BG_SECONDARY,
                                                       foreground=self.COLOR_TEXT_PRIMARY,
                                                       insertbackground=self.COLOR_TEXT_PRIMARY, # Couleur du curseur
                                                       relief=tk.FLAT, borderwidth=1)
        self.resultats_text.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        
        # --- Menu contextuel pour la zone de résultats ---
        self.results_context_menu = tk.Menu(self.resultats_text, tearoff=0,
                                            background=self.COLOR_BG_SECONDARY, # Appliquer le style
                                            foreground=self.COLOR_TEXT_PRIMARY,
                                            activebackground=self.COLOR_ACCENT,
                                            activeforeground=self.COLOR_TEXT_PRIMARY)
        # Les labels seront mis à jour dynamiquement. Les commandes ne font rien.
        self.results_context_menu.add_command(label="Hits: 0", state=tk.DISABLED) # Index 0
        self.results_context_menu.add_command(label="Erreurs: 0", state=tk.DISABLED) # Index 1
        self.results_context_menu.add_command(label="Doublons évités: 0", state=tk.DISABLED) # Index 2
        self.results_context_menu.add_separator() # Index 3
        self.results_context_menu.add_command(label="Sauvegarder les résultats...", command=self._save_results) # Index 4
        self.resultats_text.bind("<Button-3>", self._show_results_context_menu) # Clic droit

        self._reconfigure_result_tags() # Appliquer les styles de tag initiaux

        # --- Progress Bar and Status Label Frame ---
        progress_status_frame = ttk.Frame(self.main_view_frame)
        progress_status_frame.pack(fill=tk.X)

        self.duplicates_label = ttk.Label(progress_status_frame, text="") # Label pour les doublons
        self.duplicates_label.pack(side=tk.LEFT, padx=(0, 5)) # Packé à gauche en premier

        self.progress_bar = ttk.Progressbar(progress_status_frame, orient=tk.HORIZONTAL, mode='determinate', length=200)
        self.progress_bar.pack(side=tk.RIGHT, padx=(5, 0)) # Packé à droite ensuite

        self.progress_label = ttk.Label(progress_status_frame, text="Prêt") # Label d'état
        self.progress_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5) # Packé pour remplir l'espace restant

    def _build_settings_view(self):
        """Construit l'interface utilisateur de la page des paramètres."""
        self.settings_view_frame = ttk.Frame(self.content_host_frame, padding="10")
        # self.settings_view_frame.pack_forget() # Déjà géré dans _init_ui

        # Création du Notebook (onglets)
        notebook = ttk.Notebook(self.settings_view_frame)
        notebook.pack(expand=True, fill='both', pady=10)

        # --- Onglet Thème ---
        theme_tab = ttk.Frame(notebook, padding="10")
        notebook.add(theme_tab, text='Thème')
        ttk.Label(theme_tab, text="Choisissez votre thème pref <3 :").pack(anchor='w', pady=(0,10))

        for theme_name in self.themes:
            rb = ttk.Radiobutton(theme_tab, text=theme_name, variable=self.selected_theme_var, value=theme_name)
            rb.pack(anchor='w', padx=10, pady=2)

        apply_theme_button = ttk.Button(theme_tab, text="Appliquer le Thème", command=self._apply_selected_theme)
        apply_theme_button.pack(pady=10)

        # --- Onglet Info Supplémentaire ---
        info_tab = ttk.Frame(notebook, padding="10")
        notebook.add(info_tab, text='Info supplémentaire')
        ttk.Label(info_tab, text="Informations en plus:").pack(anchor='w', pady=(0,10))
        ttk.Label(info_tab, text="Version: 3.0 BETA").pack(anchor='w')
        ttk.Label(info_tab, text="Développeur: Saucisson.flp").pack(anchor='w')

        # --- Onglet Crédits ---
        credits_tab = ttk.Frame(notebook, padding="10")
        notebook.add(credits_tab, text='Crédits')
        ttk.Label(credits_tab, text="Remerciements:").pack(anchor='w', pady=(0,10))
        ttk.Label(credits_tab, text="- Python ( ptn merci )").pack(anchor='w')
        ttk.Label(credits_tab, text="- Tkinter / Ttk").pack(anchor='w')
        ttk.Label(credits_tab, text="- PyQt5 / Sunset").pack(anchor='w')

        # --- Onglet Affichage ---
        affichage_tab = ttk.Frame(notebook, padding="10")
        notebook.add(affichage_tab, text='Affichage')

        ttk.Label(affichage_tab, text="Police des résultats:").pack(anchor='w', pady=(5,0))
        self.font_family_combo = ttk.Combobox(affichage_tab, textvariable=self.selected_font_family_var, values=sorted(list(tkFont.families())), state="readonly")
        self.font_family_combo.pack(fill='x', pady=(0,5))

        ttk.Label(affichage_tab, text="Taille de la police des résultats:").pack(anchor='w', pady=(5,0))
        self.font_size_spinbox = ttk.Spinbox(affichage_tab, from_=6, to=30, increment=1, textvariable=self.selected_font_size_var, width=5)
        self.font_size_spinbox.pack(anchor='w', pady=(0,10))

        # Couleur [NEW]
        new_color_frame = ttk.Frame(affichage_tab)
        new_color_frame.pack(fill='x', pady=(5,0))
        ttk.Label(new_color_frame, text="Couleur résultats [NEW]:").pack(side=tk.LEFT, padx=(0,5))
        self.new_item_color_entry = ttk.Entry(new_color_frame, textvariable=self.new_item_color_var, width=10)
        self.new_item_color_entry.pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(new_color_frame, text="Choisir...", command=lambda: self._pick_color(self.new_item_color_var)).pack(side=tk.LEFT)

        # Couleur [ERREUR]
        error_color_frame = ttk.Frame(affichage_tab)
        error_color_frame.pack(fill='x', pady=(5,0))
        ttk.Label(error_color_frame, text="Couleur résultats [ERREUR]:").pack(side=tk.LEFT, padx=(0,5))
        self.error_item_color_entry = ttk.Entry(error_color_frame, textvariable=self.error_item_color_var, width=10)
        self.error_item_color_entry.pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(error_color_frame, text="Choisir...", command=lambda: self._pick_color(self.error_item_color_var)).pack(side=tk.LEFT)

        apply_display_button = ttk.Button(affichage_tab, text="Appliquer Affichage", command=self._apply_display_settings_and_update_theme)
        apply_display_button.pack(pady=20)

        # --- Onglet Recherche ---
        recherche_tab_container = ttk.Frame(notebook, padding=0) # Container pour le canvas et la scrollbar
        notebook.add(recherche_tab_container, text='Recherche')

        recherche_canvas = tk.Canvas(recherche_tab_container, bg=self.COLOR_BG_PRIMARY, highlightthickness=0)
        recherche_scrollbar = ttk.Scrollbar(recherche_tab_container, orient="vertical", command=recherche_canvas.yview)
        
        # Frame scrollable à l'intérieur du canvas
        scrollable_frame_recherche = ttk.Frame(recherche_canvas, padding="10")
        
        # Lier la scrollbar au canvas
        recherche_canvas.configure(yscrollcommand=recherche_scrollbar.set)
        
        # Placer le frame scrollable dans le canvas
        recherche_canvas.create_window((0, 0), window=scrollable_frame_recherche, anchor="nw")

        # Mettre à jour la région de défilement du canvas lorsque la taille du frame change
        scrollable_frame_recherche.bind("<Configure>", lambda e: recherche_canvas.configure(scrollregion=recherche_canvas.bbox("all")))

        # Empaqueter le canvas et la scrollbar
        recherche_canvas.pack(side="left", fill="both", expand=True)
        recherche_scrollbar.pack(side="right", fill="y")

        # Fonction pour le défilement à la molette
        def _on_mousewheel_recherche(event):
            recherche_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        recherche_canvas.bind_all("<MouseWheel>", _on_mousewheel_recherche) # Bind sur tout le canvas

        # --- Contenu de l'onglet Recherche (maintenant dans scrollable_frame_recherche) ---
        ttk.Label(scrollable_frame_recherche, text="Extensions de fichiers autorisées (séparées par des virgules, ex: .txt,.log,.data):").pack(anchor='w', pady=(5,2))
        self.extensions_entry = ttk.Entry(scrollable_frame_recherche, textvariable=self.extensions_str_var, width=50)
        self.extensions_entry.pack(fill='x', pady=(0,10))
        
        self.filter_duplicates_checkbutton = ttk.Checkbutton(scrollable_frame_recherche, text="Filtrer les résultats en double", variable=self.filter_duplicates_var)
        self.filter_duplicates_checkbutton.pack(anchor='w', pady=(5,10))

        self.case_sensitive_checkbutton = ttk.Checkbutton(scrollable_frame_recherche, text="Recherche sensible à la casse", variable=self.case_sensitive_var)
        self.case_sensitive_checkbutton.pack(anchor='w', pady=(5,0)) # Réduction du pady en bas
        ttk.Label(scrollable_frame_recherche, text="Coché : 'Mot' ne trouvera pas 'mot'. Décoché : 'Mot' trouvera 'mot'.", font=(self.DEFAULT_FONT_FAMILY, max(6, self.DEFAULT_FONT_SIZE - 2) )).pack(anchor='w', padx=(20,0), pady=(0,10)) # Ajout du texte explicatif

        ttk.Label(scrollable_frame_recherche, text="Nombre max de processus de recherche (workers):").pack(anchor='w', pady=(10,0))
        max_cpu_workers = os.cpu_count() or 1
        self.workers_spinbox = ttk.Spinbox(scrollable_frame_recherche, from_=1, to=max(32, max_cpu_workers * 2), increment=1, textvariable=self.max_workers_var, width=5)
        self.workers_spinbox.pack(anchor='w', pady=(0,2))
        explanation_text = "Plus de workers peuvent accélérer la recherche sur CPU multi-cœurs mais consomment plus de ressources.\nUn nombre excessif peut être contre-productif. N'affecte pas vos fichiers."
        ttk.Label(scrollable_frame_recherche, text=explanation_text, font=(self.DEFAULT_FONT_FAMILY, max(6, self.DEFAULT_FONT_SIZE - 2) )).pack(anchor='w', pady=(0,10))
        ttk.Label(scrollable_frame_recherche, text="Dossiers/Fichiers à exclure (noms ou parties de chemin, séparés par virgules):").pack(anchor='w', pady=(10,2))
        self.excluded_paths_entry = ttk.Entry(scrollable_frame_recherche, textvariable=self.excluded_paths_str_var, width=50)
        self.excluded_paths_entry.pack(fill='x', pady=(0,10))
        apply_search_settings_button = ttk.Button(scrollable_frame_recherche, text="Appliquer Paramètres de Recherche", command=self._apply_search_settings)
        apply_search_settings_button.pack(pady=(15,10))

    def _apply_styles(self):
        style = ttk.Style()
        style.theme_use('clam') # Base theme, 'clam' est souvent bon pour la personnalisation

        style.configure('.', background=self.COLOR_BG_PRIMARY, foreground=self.COLOR_TEXT_PRIMARY) # Style global
        style.configure('TFrame', background=self.COLOR_BG_PRIMARY)
        style.configure('TLabel', background=self.COLOR_BG_PRIMARY, foreground=self.COLOR_TEXT_PRIMARY)
        style.configure('TButton', background=self.COLOR_ACCENT, foreground=self.COLOR_TEXT_PRIMARY, relief=tk.FLAT, borderwidth=0)
        style.map('TButton', background=[('active', self.COLOR_TEXT_ACCENT)])
        style.configure('Accent.TButton', background=self.COLOR_TEXT_ACCENT, foreground=self.COLOR_BG_PRIMARY, relief=tk.FLAT, borderwidth=0) # Bouton "Rechercher"
        style.map('Accent.TButton', background=[('active', self.COLOR_ACCENT)])
        # Style normal pour TEntry (utilisé quand il y a du texte utilisateur)
        style.configure('TEntry', fieldbackground=self.COLOR_BG_SECONDARY, foreground=self.COLOR_TEXT_PRIMARY, insertcolor=self.COLOR_TEXT_PRIMARY, relief=tk.FLAT, borderwidth=1)
        # Style pour TEntry quand il affiche le placeholder
        style.configure('Placeholder.TEntry', fieldbackground=self.COLOR_BG_SECONDARY, foreground=self.COLOR_TEXT_ACCENT, insertcolor=self.COLOR_TEXT_PRIMARY, relief=tk.FLAT, borderwidth=1)
        style.configure('TProgressbar', troughcolor=self.COLOR_BG_SECONDARY, background=self.COLOR_ACCENT, thickness=15, relief=tk.FLAT, borderwidth=0)

        # Style pour TSpinbox pour assurer la visibilité du texte dans son champ d'entrée
        style.configure('TSpinbox',
                        fieldbackground=self.COLOR_BG_SECONDARY,
                        foreground=self.COLOR_TEXT_PRIMARY,
                        insertcolor=self.COLOR_TEXT_PRIMARY,
                        relief=tk.FLAT) # Vous pouvez ajouter borderwidth=1 si nécessaire

        # Style pour les onglets du Notebook
        style.configure('TNotebook', background=self.COLOR_BG_PRIMARY, borderwidth=0)
        style.configure('TNotebook.Tab', background=self.COLOR_BG_SECONDARY, foreground=self.COLOR_TEXT_PRIMARY, padding=[5, 2], borderwidth=0)
        style.map('TNotebook.Tab',
                  background=[('selected', self.COLOR_ACCENT), ('active', self.COLOR_BG_SECONDARY)],
                  foreground=[('selected', self.COLOR_TEXT_PRIMARY), ('active', self.COLOR_TEXT_ACCENT)])

        # Lier les événements pour le déplacement de la fenêtre à la barre de titre et au label
        self.title_bar.bind("<ButtonPress-1>", self._on_press_title_bar)
        self.title_bar.bind("<B1-Motion>", self._on_drag_title_bar)
        self.title_label.bind("<ButtonPress-1>", self._on_press_title_bar)
        self.title_label.bind("<B1-Motion>", self._on_drag_title_bar)

    def _put_on_ui_queue(self, *args):
        """Helper pour mettre des messages dans la file d'attente de l'UI."""
        self.ui_queue.put(args)

    def _process_ui_queue(self):
        """Traite les messages de la file d'attente pour mettre à jour l'UI dans le thread principal."""
        try:
            while True:
                message = self.ui_queue.get_nowait()
                msg_type = message[0]

                if msg_type == "append_text":
                    _, text_content, tag_name = message # tag_name peut être "new_item", "error_item", ou None
                    self.resultats_text.configure(state='normal')
                    if tag_name == "new_item" and text_content.startswith("[NEW] "):
                        prefix = "[NEW] "
                        actual_content = text_content[len(prefix):]
                        self.resultats_text.insert(tk.END, prefix, "new_item")
                        self.resultats_text.insert(tk.END, actual_content + "\n") # Le reste avec le style par défaut
                    elif tag_name: # Pour "error_item" ou d'autres tags spécifiques
                        self.resultats_text.insert(tk.END, text_content + "\n", tag_name)
                    else: # Pour les messages sans tag spécifique (style par défaut)
                        self.resultats_text.insert(tk.END, text_content + "\n")
                    self.resultats_text.see(tk.END) # Faire défiler vers la fin
                    self.resultats_text.configure(state='disabled')
                elif msg_type == "clear_text":
                    self.resultats_text.configure(state='normal')
                    self.resultats_text.delete('1.0', tk.END)
                    self.resultats_text.configure(state='disabled')
                elif msg_type == "progress_update":
                    _, value, max_val = message
                    if self.progress_bar['maximum'] != max_val:
                        self.progress_bar['maximum'] = max_val
                    self.progress_bar['value'] = value
                elif msg_type == "status_label":
                    _, text_content = message
                    self.progress_label.config(text=text_content)
                elif msg_type == "duplicates_info":
                    _, text_content = message
                    self.duplicates_label.config(text=text_content)
                elif msg_type == "search_stats_update":
                    _, hits, errors, duplicates = message
                    self.search_hits_count = hits
                    self.search_errors_count = errors
                    self.search_duplicates_count = duplicates
                    if hasattr(self, 'results_context_menu'):
                        self.results_context_menu.entryconfigure(0, label=f"Hits: {self.search_hits_count}", state=tk.NORMAL if self.search_hits_count >= 0 else tk.DISABLED) # Toujours NORMAL ou basé sur >0
                        self.results_context_menu.entryconfigure(1, label=f"Erreurs: {self.search_errors_count}", state=tk.NORMAL if self.search_errors_count >= 0 else tk.DISABLED)
                        self.results_context_menu.entryconfigure(2, label=f"Doublons évités: {self.search_duplicates_count}", state=tk.NORMAL if self.search_duplicates_count >= 0 else tk.DISABLED)
        except queue.Empty:
            pass # Normal, la file est vide
        finally:
            self.master.after(100, self._process_ui_queue) # Planifier la prochaine vérification

    def _on_press_title_bar(self, event):
        """Enregistre la position du clic initial sur la barre de titre."""
        self._offset_x = event.x
        self._offset_y = event.y

    def _on_drag_title_bar(self, event):
        """Déplace la fenêtre en fonction du glissement de la souris."""
        x = self.master.winfo_pointerx() - self._offset_x
        y = self.master.winfo_pointery() - self._offset_y
        self.master.geometry(f"+{x}+{y}")

    def _animate_fade_in(self, current_alpha=0.0):
        """Anime l'apparition de la fenêtre (fade-in)."""
        if current_alpha < 1.0:
            current_alpha += 0.05 # Augmente l'opacité par pas de 5%
            self.master.attributes('-alpha', min(current_alpha, 1.0)) # Assure de ne pas dépasser 1.0
            self.master.after(20, lambda: self._animate_fade_in(current_alpha)) # Répète après 20ms
        else:
            self.master.attributes('-alpha', 1.0) # S'assurer que c'est complètement opaque

    def _toggle_view(self):
        """Bascule entre la vue principale et la vue des paramètres."""
        if self.current_view_frame == self.main_view_frame:
            self.main_view_frame.pack_forget()
            self.settings_view_frame.pack(fill=tk.BOTH, expand=True)
            self.current_view_frame = self.settings_view_frame
            self.title_label.config(text=f"{self.master.title()} - Paramètres")
        else:
            self.settings_view_frame.pack_forget()
            self.main_view_frame.pack(fill=tk.BOTH, expand=True)
            self.current_view_frame = self.main_view_frame
            self.title_label.config(text=self.master.title())

    def _apply_selected_theme(self):
        new_theme_name = self.selected_theme_var.get()
        if new_theme_name != self.current_theme_name:
            self._load_theme_settings(new_theme_name) # Charge tous les paramètres, y compris affichage
            self.current_theme_name = new_theme_name
            
            # Réappliquer les styles et les configurations directes
            self._apply_styles() # Pour les widgets ttk

            # Mise à jour manuelle des widgets tk et des conteneurs principaux
            if _ctypes_available and platform.system() == "Windows":
                # La couleur de fond de master est la couleur de transparence
                pass # Ne pas changer master.configure(bg=...) ici si on garde la même TRANSPARENT_COLOR
            
            self.root_container.configure(bg=self.COLOR_BG_PRIMARY)
            self.title_bar.configure(bg=self.COLOR_TITLE_BAR_BG)
            self.title_label.configure(bg=self.COLOR_TITLE_BAR_BG, fg=self.COLOR_TEXT_PRIMARY)
            self.close_button.configure(bg=self.COLOR_TITLE_BAR_BG, fg=self.COLOR_TEXT_PRIMARY) # activebackground/fg restent
            self.settings_button.configure(bg=self.COLOR_TITLE_BAR_BG, fg=self.COLOR_TEXT_PRIMARY, activebackground=self.COLOR_ACCENT)
            self.separator_line.configure(bg=self.COLOR_TITLE_BAR_BORDER)

            # Mettre à jour les vues (elles utilisent ttk.Frame, donc _apply_styles devrait suffire pour leur fond)
            # mais leur contenu peut nécessiter une attention si des couleurs sont codées en dur.
            # Pour l'instant, on se concentre sur les éléments globaux.
            # ScrolledText
            self.resultats_text.configure(background=self.COLOR_BG_SECONDARY, foreground=self.COLOR_TEXT_PRIMARY, insertbackground=self.COLOR_TEXT_PRIMARY)
            
            # Mettre à jour les variables des widgets de l'onglet Affichage
            self.selected_font_family_var.set(self.FONT_FAMILY_RESULTS)
            self.selected_font_size_var.set(self.FONT_SIZE_RESULTS)
            self.new_item_color_var.set(self.COLOR_RESULT_NEW)
            self.error_item_color_var.set(self.COLOR_RESULT_ERROR)

            self._reconfigure_result_tags() # Appliquer les nouveaux paramètres d'affichage du thème
            self._save_app_settings() # Sauvegarder après changement de thème

    def _pick_color(self, target_var):
        """Ouvre un sélecteur de couleur et met à jour la variable cible."""
        color_code = colorchooser.askcolor(title="Choisir une couleur", initialcolor=target_var.get())
        if color_code and color_code[1]: # color_code[1] est la couleur en hex
            target_var.set(color_code[1])

    def _apply_display_settings_and_update_theme(self):
        """Applique les paramètres d'affichage modifiés et met à jour le thème actuel."""
        self.FONT_FAMILY_RESULTS = self.selected_font_family_var.get()
        self.FONT_SIZE_RESULTS = self.selected_font_size_var.get()
        self.COLOR_RESULT_NEW = self.new_item_color_var.get()
        self.COLOR_RESULT_ERROR = self.error_item_color_var.get()

        # Mettre à jour le dictionnaire du thème actuel
        current_theme_dict = self.themes[self.current_theme_name]
        current_theme_dict["FONT_FAMILY_RESULTS"] = self.FONT_FAMILY_RESULTS
        current_theme_dict["FONT_SIZE_RESULTS"] = self.FONT_SIZE_RESULTS
        current_theme_dict["COLOR_RESULT_NEW"] = self.COLOR_RESULT_NEW
        current_theme_dict["COLOR_RESULT_ERROR"] = self.COLOR_RESULT_ERROR

        self._reconfigure_result_tags()
        self._save_app_settings() # Sauvegarder après application des paramètres d'affichage

    def _parse_excluded_paths(self, paths_string):
        """Nettoie et parse la chaîne de chemins/noms à exclure. Convertit en minuscules."""
        if not paths_string.strip():
            return []
        # Les éléments sont stockés en minuscules pour une comparaison insensible à la casse.
        excluded_list = [p.strip().lower() for p in paths_string.split(',') if p.strip()]
        return list(set(excluded_list)) # Remove duplicates
        self._save_app_settings() # Sauvegarder après application des paramètres d'affichage

    def _parse_extensions(self, ext_string):
        """Nettoie et parse la chaîne d'extensions."""
        if not ext_string.strip():
            return [] # Permet à l'utilisateur de ne spécifier aucune extension
        
        raw_extensions = [ext.strip().lower() for ext in ext_string.split(',') if ext.strip()]
        parsed_extensions = []
        for ext in raw_extensions:
            if not ext.startswith('.'):
                ext = '.' + ext
            parsed_extensions.append(ext)
        return list(set(parsed_extensions)) # Supprime les doublons

    def _apply_search_settings(self):
        """Applique les paramètres de recherche modifiés (extensions, filtrage doublons)."""
        # Extensions
        new_ext_str = self.extensions_str_var.get()
        parsed_list = self._parse_extensions(new_ext_str)
        self.current_extensions_list = parsed_list
        self.extensions_str_var.set(",".join(self.current_extensions_list))

        # Filtrage des doublons
        self.filter_duplicates_enabled = self.filter_duplicates_var.get()

        # Nombre de workers
        self.case_sensitive_search = self.case_sensitive_var.get()
        try:
            self.current_max_workers = max(1, self.max_workers_var.get()) # S'assurer qu'il y a au moins 1 worker
        except tk.TclError: # Au cas où la valeur ne serait pas un entier valide
            self.current_max_workers = self.DEFAULT_MAX_WORKERS
            self.max_workers_var.set(self.current_max_workers)

        # Exclusions
        new_excluded_str = self.excluded_paths_str_var.get()
        self.current_excluded_paths_list = self._parse_excluded_paths(new_excluded_str)
        self.excluded_paths_str_var.set(",".join(self.current_excluded_paths_list)) # Mettre à jour l'UI avec la liste nettoyée

        self._put_on_ui_queue("status_label", "Paramètres de recherche mis à jour.") # TODO: Traduire
        self._save_app_settings() # Sauvegarder après application des paramètres de recherche

    def _animate_placeholder_disappear(self):
        self._is_placeholder_animating = True
        current_text = self.batabase_input.get()

        # Conditions d'arrêt: focus perdu, ou le texte n'est plus le début du placeholder
        if self.master.focus_get() != self.batabase_input or \
           not self.PLACEHOLDER_TEXT_DB_INPUT.startswith(current_text) or \
           not current_text: # Si vide (au cas où)
            self._is_placeholder_animating = False
            if self.master.focus_get() == self.batabase_input and not self.batabase_input.get():
                self.batabase_input.configure(style='TEntry') # Style normal si focus et vide
            # Si le texte a été modifié par l'utilisateur pour ne plus être le placeholder
            elif self.master.focus_get() == self.batabase_input and current_text and not self.PLACEHOLDER_TEXT_DB_INPUT.startswith(current_text):
                 self.batabase_input.configure(style='TEntry')
            return

        self.batabase_input.delete(len(current_text) - 1, tk.END)

        if len(self.batabase_input.get()) > 0:
            self._placeholder_disappear_job_id = self.master.after(35, self._animate_placeholder_disappear)
        else: # Tout est effacé
            self._is_placeholder_animating = False
            if self.master.focus_get() == self.batabase_input: # S'assurer que le focus est toujours là
                self.batabase_input.configure(style='TEntry')

    def _animate_placeholder_appear(self, index=0):
        self._is_placeholder_animating = True

        # Condition d'arrêt: focus regagné par l'utilisateur ou texte déjà présent/différent
        if self.master.focus_get() == self.batabase_input or \
           (self.batabase_input.get() and self.batabase_input.get() != self.PLACEHOLDER_TEXT_DB_INPUT[:index]):
            self._is_placeholder_animating = False
            # Si le focus est revenu et que le champ est vide ou contient un début de placeholder, _on_db_input_focus_in s'en chargera.
            # Si l'utilisateur a tapé quelque chose, on ne touche plus.
            return

        if index == 0: # Au début de l'animation d'apparition, s'assurer que le champ est vide
            self.batabase_input.delete(0, tk.END)

        self.batabase_input.insert(tk.END, self.PLACEHOLDER_TEXT_DB_INPUT[index])

        if index < len(self.PLACEHOLDER_TEXT_DB_INPUT) - 1:
            self._placeholder_appear_job_id = self.master.after(35, lambda: self._animate_placeholder_appear(index + 1))
        else:
            self._is_placeholder_animating = False
            # S'assurer que le style est correct à la fin de l'animation
            if self.batabase_input.get() == self.PLACEHOLDER_TEXT_DB_INPUT:
                 self.batabase_input.configure(style='Placeholder.TEntry')

    def _on_db_input_focus_in(self, event):
        """Gère l'événement FocusIn pour le champ de saisie de la base de données."""
        if self._placeholder_appear_job_id: # Si l'animation d'apparition était en cours
            self.master.after_cancel(self._placeholder_appear_job_id)
            self._placeholder_appear_job_id = None
            self._is_placeholder_animating = False
        
        current_text = self.batabase_input.get()
        if self.PLACEHOLDER_TEXT_DB_INPUT.startswith(current_text) and \
           self.batabase_input.cget('style') == 'Placeholder.TEntry':
            if not self._is_placeholder_animating:
                self._animate_placeholder_disappear()
        elif not current_text: # Si c'est vide pour une raison quelconque (ex: animation interrompue)
             self.batabase_input.configure(style='TEntry') # Passer au style normal

    def _on_db_input_focus_out(self, event):
        """Gère l'événement FocusOut pour le champ de saisie de la base de données."""
        if self._placeholder_disappear_job_id: # Si l'animation de disparition était en cours
            self.master.after_cancel(self._placeholder_disappear_job_id)
            self._placeholder_disappear_job_id = None
            self._is_placeholder_animating = False

        if not self.batabase_input.get():
            self.batabase_input.configure(style='Placeholder.TEntry')
            if not self._is_placeholder_animating: # Ne pas démarrer si déjà en cours
                self._animate_placeholder_appear()

    def _on_db_input_keyrelease(self, event):
        """Gère la frappe de touche pour s'assurer que le style est correct."""
        # Si l'utilisateur tape pendant l'animation de disparition du placeholder
        if self._is_placeholder_animating and self._placeholder_disappear_job_id:
            current_text = self.batabase_input.get()
            # Si le texte tapé par l'utilisateur ne correspond plus au début du placeholder
            if not self.PLACEHOLDER_TEXT_DB_INPUT.startswith(current_text):
                self.master.after_cancel(self._placeholder_disappear_job_id)
                self._placeholder_disappear_job_id = None
                self._is_placeholder_animating = False
                self.batabase_input.configure(style='TEntry') # Passer au style normal
        elif not self._is_placeholder_animating and self.batabase_input.get() and self.batabase_input.cget('style') == 'Placeholder.TEntry':
            # Si pas d'animation en cours, mais l'utilisateur tape dans un champ stylé placeholder
            self.batabase_input.configure(style='TEntry')

    def _reconfigure_result_tags(self):
        """Reconfigure les tags pour la zone de texte des résultats en fonction des paramètres actuels."""
        if not hasattr(self, 'resultats_text'): # S'assurer que le widget existe
            return
        try:
            font_family = self.FONT_FAMILY_RESULTS
            font_size = int(self.FONT_SIZE_RESULTS) # S'assurer que c'est un entier
            
            self.resultats_text.tag_configure("new_item", 
                                              foreground=self.COLOR_RESULT_NEW, 
                                              font=(font_family, font_size, 'bold'))
            self.resultats_text.tag_configure("error_item", 
                                              foreground=self.COLOR_RESULT_ERROR,
                                              font=(font_family, font_size)) # Les erreurs ne sont pas en gras par défaut
        except ValueError:
            print(f"Erreur: La taille de la police '{self.FONT_SIZE_RESULTS}' n'est pas un nombre valide.")
            # Optionnel: réinitialiser à une valeur par défaut sûre
            # self.resultats_text.tag_configure("new_item", font=(self.DEFAULT_FONT_FAMILY, self.DEFAULT_FONT_SIZE, 'bold'))
            # self.resultats_text.tag_configure("error_item", font=(self.DEFAULT_FONT_FAMILY, self.DEFAULT_FONT_SIZE))
        except Exception as e:
            print(f"Erreur lors de la reconfiguration des tags de résultat: {e}")

    def _show_results_context_menu(self, event):
        """Affiche le menu contextuel pour la zone de résultats."""
        self.results_context_menu.tk_popup(event.x_root, event.y_root)


    def _save_results(self):
        """Sauvegarde le contenu de la zone de résultats dans un fichier."""
        results_content = self.resultats_text.get("1.0", tk.END).strip()
        if not results_content:
            self._put_on_ui_queue("status_label", "Aucun résultat à sauvegarder.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Fichiers Texte", "*.txt"), ("Tous les fichiers", "*.*")],
            title="Sauvegarder les résultats"
        )

        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(results_content)
                self._put_on_ui_queue("status_label", f"Résultats sauvegardés dans {os.path.basename(filepath)}")
            except Exception as e:
                self._put_on_ui_queue("status_label", f"Erreur lors de la sauvegarde: {e}")
                print(f"Erreur de sauvegarde: {e}")

    def _save_app_settings(self):
        """Sauvegarde les paramètres actuels de l'application dans un fichier JSON."""
        settings_to_save = {
            "current_theme_name": self.current_theme_name,
            # Les couleurs et polices des résultats sont maintenant spécifiques au thème,
            # mais si on veut les sauvegarder comme des overrides utilisateur:
            "font_family_results": self.FONT_FAMILY_RESULTS,
            "font_size_results": self.FONT_SIZE_RESULTS,
            "color_result_new": self.COLOR_RESULT_NEW,
            "color_result_error": self.COLOR_RESULT_ERROR,
            "current_extensions_list": self.current_extensions_list,
            "filter_duplicates_enabled": self.filter_duplicates_enabled,
            "current_max_workers": self.current_max_workers,
            "current_excluded_paths_list": self.current_excluded_paths_list,
            "case_sensitive_search": self.case_sensitive_var.get(),
            # "current_language": self.current_language # Si la fonctionnalité de langue est ajoutée
        }
        try:
            with open(self.CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(settings_to_save, f, indent=4)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des paramètres: {e}")

    def _load_app_settings(self):
        """Charge les paramètres de l'application depuis un fichier JSON."""
        try:
            if os.path.exists(self.CONFIG_FILE_PATH):
                with open(self.CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    loaded_settings = json.load(f)

                # Appliquer le thème chargé
                self.current_theme_name = loaded_settings.get("current_theme_name", self.current_theme_name)
                self._load_theme_settings(self.current_theme_name) # Charge les bases du thème

                # Appliquer les overrides spécifiques si présents dans le fichier de config
                # Ces valeurs remplaceront celles du thème chargé ci-dessus
                self.FONT_FAMILY_RESULTS = loaded_settings.get("font_family_results", self.FONT_FAMILY_RESULTS)
                self.FONT_SIZE_RESULTS = loaded_settings.get("font_size_results", self.FONT_SIZE_RESULTS)
                self.COLOR_RESULT_NEW = loaded_settings.get("color_result_new", self.COLOR_RESULT_NEW)
                self.COLOR_RESULT_ERROR = loaded_settings.get("color_result_error", self.COLOR_RESULT_ERROR)

                self.current_extensions_list = loaded_settings.get("current_extensions_list", self.current_extensions_list)
                self.filter_duplicates_enabled = loaded_settings.get("filter_duplicates_enabled", self.filter_duplicates_enabled)
                self.current_max_workers = loaded_settings.get("current_max_workers", self.current_max_workers)
                self.current_excluded_paths_list = loaded_settings.get("current_excluded_paths_list", self.current_excluded_paths_list)
                self.case_sensitive_search = loaded_settings.get("case_sensitive_search", False) # False par défaut si non trouvé

                # Mettre à jour les StringVars après le chargement pour refléter dans l'UI
                self.extensions_str_var.set(",".join(self.current_extensions_list))
                self.filter_duplicates_var.set(self.filter_duplicates_enabled)
                self.max_workers_var.set(self.current_max_workers)
                self.excluded_paths_str_var.set(",".join(self.current_excluded_paths_list))
                self.case_sensitive_var.set(self.case_sensitive_search)
                # self.current_language = loaded_settings.get("current_language", self.current_language)
                # if hasattr(self, 'translations'): # Si la gestion de langue est active
                #     self.translations = self.languages.get(self.current_language, self.languages["Français"])

                # Mettre à jour le dictionnaire du thème actuel avec les valeurs chargées (si elles étaient des overrides)
                # Cela garantit que si l'utilisateur modifie ensuite l'affichage via l'UI,
                # ces modifications sont basées sur ce qui a été chargé, et non sur les défauts du thème.
                current_theme_dict = self.themes[self.current_theme_name]
                current_theme_dict["FONT_FAMILY_RESULTS"] = self.FONT_FAMILY_RESULTS
                current_theme_dict["FONT_SIZE_RESULTS"] = self.FONT_SIZE_RESULTS
                current_theme_dict["COLOR_RESULT_NEW"] = self.COLOR_RESULT_NEW
                current_theme_dict["COLOR_RESULT_ERROR"] = self.COLOR_RESULT_ERROR

        except Exception as e:
            print(f"Erreur lors du chargement des paramètres (utilisation des valeurs par défaut): {e}")
            # En cas d'erreur, les valeurs par défaut initialisées avant cet appel seront utilisées.

    def _apply_rounded_corners_windows(self, radius):
        """Applique des coins arrondis à la fenêtre principale sur Windows."""
        if not _ctypes_available:
            return
        try:
            self.master.update_idletasks() # S'assurer que les dimensions sont à jour
            hwnd = self.master.winfo_id()
            
            width = self.master.winfo_width()
            height = self.master.winfo_height()

            if width <= 1 or height <= 1: # Fenêtre minimisée ou pas encore complètement dessinée
                return 

            # CreateRoundRectRgn(xLeftRect, yTopRect, xRightRect, yBottomRect, nWidthEllipse, nHeightEllipse)
            hRgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width, height, radius, radius)
            
            # SetWindowRgn(hWnd, hRgn, bRedraw)
            # Le troisième argument True indique que le système doit redessiner la fenêtre.
            # Le système prend possession de hRgn, il ne faut pas le supprimer avec DeleteObject.
            ctypes.windll.user32.SetWindowRgn(hwnd, hRgn, True)

        except Exception as e:
            print(f"Erreur lors de l'application des coins arrondis (Windows): {e}")
        """Applique des coins arrondis à la fenêtre principale sur Windows."""
        if not _ctypes_available:
            return
        try:
            self.master.update_idletasks() # S'assurer que les dimensions sont à jour
            hwnd = self.master.winfo_id()
            
            width = self.master.winfo_width()
            height = self.master.winfo_height()

            if width <= 1 or height <= 1: # Fenêtre minimisée ou pas encore complètement dessinée
                return 

            # CreateRoundRectRgn(xLeftRect, yTopRect, xRightRect, yBottomRect, nWidthEllipse, nHeightEllipse)
            hRgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width, height, radius, radius)
            
            # SetWindowRgn(hWnd, hRgn, bRedraw)
            # Le troisième argument True indique que le système doit redessiner la fenêtre.
            # Le système prend possession de hRgn, il ne faut pas le supprimer avec DeleteObject.
            ctypes.windll.user32.SetWindowRgn(hwnd, hRgn, True)

        except Exception as e:
            print(f"Erreur lors de l'application des coins arrondis (Windows): {e}")

    def _on_window_configure_for_rounding(self, event, radius):
        """Réapplique les coins arrondis lorsque la fenêtre est redimensionnée."""
        if _ctypes_available:
            self._apply_rounded_corners_windows(radius)

    def _on_closing(self):
        """Gère les actions à effectuer avant la fermeture de l'application."""
        self._save_app_settings()
        self.master.destroy()

    def _handle_dnd_folder_drop(self, event):
        """Gère le dépôt d'un fichier/dossier sur l'application."""
        # event.data est une chaîne, potentiellement une liste de chemins formatée par Tcl
        # (ex: "{C:/Chemin/Dossier1} {C:/Chemin/Fichier2}")
        # Utiliser splitlist pour gérer correctement les chemins avec des espaces.
        try:
            dropped_paths = self.master.tk.splitlist(event.data)
            if dropped_paths:
                # On prend le premier élément qui est un dossier
                for path_item in dropped_paths:
                    # Nettoyer les éventuelles accolades restantes si splitlist ne les a pas gérées
                    # (normalement, splitlist devrait bien gérer la liste Tcl)
                    # path_item = path_item.strip('{}') # Généralement pas nécessaire avec splitlist
                    if os.path.isdir(path_item):
                        self.dossier_parent = path_item
                        self._put_on_ui_queue("status_label", f"Dossier (D&D): {os.path.basename(self.dossier_parent)}")
                        return # On a trouvé un dossier, on s'arrête
                self._put_on_ui_queue("status_label", "Glisser-déposer : Aucun dossier valide trouvé.")
        except Exception as e:
            print(f"Erreur lors du traitement du glisser-déposer : {e}")

    def choisir_dossier(self):
        folder = filedialog.askdirectory(title="Choisir le dossier principal")
        if folder:
            self.dossier_parent = folder
            # Optionnel: afficher le dossier choisi dans un label ou titre
            self._put_on_ui_queue("status_label", f"Dossier: {os.path.basename(self.dossier_parent)}")

    def lancer_recherche(self):
        batabase = self.batabase_input.get()
        if self.dossier_parent and batabase and batabase != self.PLACEHOLDER_TEXT_DB_INPUT:
            # Réinitialiser les compteurs et le menu contextuel
            self.search_hits_count = 0
            self.search_errors_count = 0
            self.search_duplicates_count = 0
            if hasattr(self, 'results_context_menu'):
                self.results_context_menu.entryconfigure(0, label="Hits: 0", state=tk.DISABLED)
                self.results_context_menu.entryconfigure(1, label="Erreurs: 0", state=tk.DISABLED)
                self.results_context_menu.entryconfigure(2, label="Doublons évités: 0", state=tk.DISABLED)

            self._put_on_ui_queue("clear_text")
            self._put_on_ui_queue("progress_update", 0, 100) # Reset progress
            self._put_on_ui_queue("status_label", "Recherche en cours...")

            # Exécuter la recherche dans un thread séparé pour ne pas bloquer l'UI
            # Ce thread utilisera ProcessPoolExecutor pour les tâches de fichiers
            import threading
            thread = threading.Thread(target=self._dossiersDb_recherche_worker, 
                                      args=(self.dossier_parent, 
                                            batabase, 
                                            list(self.current_extensions_list),
                                            self.filter_duplicates_enabled,
                                            self.current_max_workers,
                                            list(self.current_excluded_paths_list),
                                            self.case_sensitive_var.get()))
            thread.daemon = True # Permet à l'app de quitter même si le thread tourne
            thread.start()
        else:
            self._put_on_ui_queue("clear_text")
            self._put_on_ui_queue("append_text", "Veuillez sélectionner un dossier et entrer une donnée à rechercher.", None)
            self._put_on_ui_queue("status_label", "Prêt")

    @staticmethod
    def recherche_DB(nom_fichier, batabase_term): # Renommé batabase en batabase_term pour éviter confusion
        # Cette méthode est maintenant appelée par _recherche_DB_process_wrapper
        # qui gère la sensibilité à la casse.
        # Pour la compatibilité, nous laissons cette signature mais elle ne sera pas directement utilisée
        # par le ProcessPoolExecutor. La logique est déplacée vers _recherche_DB_internal.
        # Alternativement, on pourrait ajouter case_sensitive ici et le passer.
        # Pour l'instant, on va créer une nouvelle méthode interne pour le worker.
        pass # La logique est maintenant dans _recherche_DB_internal

    @staticmethod
    def _recherche_DB_internal(nom_fichier, batabase_term, case_sensitive):
        resultats_fichier = []
        erreurs_fichier = []
        encodings_to_try = ['utf-8', 'latin-1', 'cp1252']

        search_term_to_use = batabase_term if case_sensitive else batabase_term.lower()

        for encoding in encodings_to_try:
            try:
                if nom_fichier.endswith('.csv'):
                    with open(nom_fichier, 'r', encoding=encoding) as fichier:
                        lecteur = csv.reader(fichier)
                        for index, ligne_champs in enumerate(lecteur, start=1):
                            champs_to_check = ligne_champs if case_sensitive else [c.lower() for c in ligne_champs]
                            if any(search_term_to_use in champ for champ in champs_to_check):
                                resultats_fichier.append((nom_fichier, index, ' | '.join(ligne_champs)))
                else:
                    with open(nom_fichier, 'r', encoding=encoding) as fichier:
                        for index, ligne_texte in enumerate(fichier, start=1):
                            ligne_to_check = ligne_texte if case_sensitive else ligne_texte.lower()
                            if search_term_to_use in ligne_to_check:
                                resultats_fichier.append((nom_fichier, index, ligne_texte.strip()))
                break # Si la lecture réussit avec cet encodage, on sort de la boucle d'encodage
            except UnicodeDecodeError:
                if encoding == encodings_to_try[-1]: # Si c'est la dernière tentative
                    erreurs_fichier.append(f"Erreur de décodage pour {os.path.basename(nom_fichier)} après toutes les tentatives.")
            except Exception as e:
                erreurs_fichier.append(f"Erreur lecture {os.path.basename(nom_fichier)} ({encoding}): {str(e)}")
                break # Erreur autre que décodage, on arrête pour ce fichier
        return resultats_fichier, erreurs_fichier

    @staticmethod
    def _recherche_DB_process_wrapper(args):
        nom_fichier, batabase_term, case_sensitive = args
        return RechercheDBAppTk._recherche_DB_internal(nom_fichier, batabase_term, case_sensitive)

    def _dossiersDb_recherche_worker(self, dossier_parent, batabase_term, extensions_list_to_use, filter_duplicates, num_workers, excluded_paths_list_to_use, case_sensitive):
        """Logique de recherche exécutée dans un thread séparé, utilisant ProcessPoolExecutor."""
        resultats = []
        fichiers_a_traiter = []
        # num_workers est maintenant passé en argument
        # excluded_paths_list_to_use contient déjà des chaînes en minuscules.
        local_hits_count = 0
        local_errors_count = 0
        found_lines_content = set() 
        duplicates_count = 0

        for dossier_racine, dirs, fichiers_in_dir in os.walk(dossier_parent):
            # Prune directories
            original_dirs = list(dirs)
            dirs[:] = [] # Modify in-place
            for d_name in original_dirs:
                dir_name_lower = d_name.lower()
                # Normaliser les séparateurs pour la comparaison de sous-chaînes
                dir_full_path_lower = os.path.join(dossier_racine, d_name).lower().replace(os.sep, '/')
                
                is_excluded = False
                for ex_item in excluded_paths_list_to_use:
                    if ex_item == dir_name_lower or ex_item in dir_full_path_lower:
                        is_excluded = True
                        break
                if not is_excluded:
                    dirs.append(d_name)

            for nom_fichier in fichiers_in_dir:
                nom_fichier_lower = nom_fichier.lower()
                chemin_fichier_lower_normalized_sep = os.path.join(dossier_racine, nom_fichier).lower().replace(os.sep, '/')
                is_excluded = any(ex_item == nom_fichier_lower or ex_item in chemin_fichier_lower_normalized_sep for ex_item in excluded_paths_list_to_use)
                if is_excluded:
                    continue

                if any(nom_fichier_lower.endswith(ext.lower()) for ext in extensions_list_to_use):
                    chemin_fichier = os.path.join(dossier_racine, nom_fichier)
                    fichiers_a_traiter.append(chemin_fichier)
        
        if not fichiers_a_traiter:
            self._put_on_ui_queue("append_text", "Aucun fichier pertinent trouvé.", None)
            self._put_on_ui_queue("status_label", "Recherche terminée (aucun fichier).")
            self._put_on_ui_queue("duplicates_info", "") # Effacer l'info des doublons
            return


        total_files = len(fichiers_a_traiter)
        self._put_on_ui_queue("progress_update", 0, total_files)
        self._put_on_ui_queue("duplicates_info", "") # Réinitialiser au début
        processed_files_count = 0
        
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Préparer les arguments pour le wrapper
            tasks_args = [(fichier, batabase_term, case_sensitive) for fichier in fichiers_a_traiter]
            futures = {executor.submit(RechercheDBAppTk._recherche_DB_process_wrapper, task_arg): task_arg[0] for task_arg in tasks_args}
            for future in as_completed(futures):
                processed_files_count += 1
                fichier = futures[future]
                
                self._put_on_ui_queue("progress_update", processed_files_count, total_files)
                self._put_on_ui_queue("status_label", f"Traitement: {os.path.basename(fichier)} ({processed_files_count}/{total_files})")

                try:
                    file_matches, file_errors = future.result()
                    for res_nom_fichier, res_index, res_ligne_content in file_matches:
                        if filter_duplicates:
                            if res_ligne_content not in found_lines_content:
                                found_lines_content.add(res_ligne_content)
                                local_hits_count +=1
                                self._put_on_ui_queue("append_text", f"[NEW] {os.path.basename(res_nom_fichier)}, L{res_index}: {res_ligne_content}", "new_item")
                            else:
                                duplicates_count += 1
                                self._put_on_ui_queue("duplicates_info", f"Doublons évités: {duplicates_count}")
                        else: # Ne pas filtrer les doublons
                            local_hits_count +=1
                            self._put_on_ui_queue("append_text", f"[NEW] {os.path.basename(res_nom_fichier)}, L{res_index}: {res_ligne_content}", "new_item")

                    for error_msg in file_errors:
                        local_errors_count +=1
                        self._put_on_ui_queue("append_text", f"[ERREUR] {error_msg}", "error_item")
                    
                    if file_matches:
                        resultats.extend(file_matches)
                except Exception as e:
                    local_errors_count +=1 # Compter aussi les erreurs de tâche
                    self._put_on_ui_queue("append_text", f"[ERREUR TÂCHE] {os.path.basename(fichier)}: {str(e)}", "error_item")
                    print(f"Erreur lors du traitement du fichier {fichier}: {str(e)}")
        
        if not resultats and processed_files_count == total_files:
             self._put_on_ui_queue("append_text", "Aucun résultat trouvé.", None)

        self._put_on_ui_queue("search_stats_update", local_hits_count, local_errors_count, duplicates_count)
        self._put_on_ui_queue("status_label", "Recherche terminée.")
        if filter_duplicates and duplicates_count > 0:
            self._put_on_ui_queue("duplicates_info", f"Doublons évités: {duplicates_count}")
        # else: # Optionnel: effacer si aucun doublon
            # self._put_on_ui_queue("duplicates_info", "") 
    
if __name__ == "__main__":
    # Nécessaire pour ProcessPoolExecutor sur certaines plateformes (Windows notamment)
    # lors de la création d'exécutables ou dans certains environnements.
    multiprocessing.freeze_support() 

    if TkinterDnD:
        root = TkinterDnD.Tk() # Utiliser TkinterDnD.Tk() si disponible
    else:
        root = tk.Tk()
        print("tkinterdnd2 non trouvé. La fonctionnalité de glisser-déposer ne sera pas disponible.")
        print("Veuillez l'installer avec : pip install tkinterdnd2")

    app = RechercheDBAppTk(root)
    root.mainloop()
