import tkinter
import tkinter.messagebox
import customtkinter
from tkinter.font import Font
customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"
import time
from collections import namedtuple
from PIL import Image


from tkinter import filedialog as fd
from tkinter.messagebox import showinfo
from ..mktorrent import python_wrapper
import os


class App(customtkinter.CTk):
    IP_PORT_ID = namedtuple("IP_PORT_ID", ["ip", "port", "id"])
    def __init__(self,
                enable_optimistic_unchoking = True,
                enable_anti_snubbing = True,
                enable_choking_strategy = True,
                enable_end_game_mode = True,
                enable_rarest_piece_first = True,
                enable_bbs_plus= True,
                enabel_dht_network=True):
        super().__init__()

        self.father_dir = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.path.sep + ".")
        print(self.father_dir)
        self.enable_optimistic_unchoking = enable_optimistic_unchoking,
        self.enable_anti_snubbing = enable_anti_snubbing,
        self.enable_choking_strategy = enable_choking_strategy,
        self.enable_end_game_mode = enable_end_game_mode,
        self.enable_rarest_piece_first = enable_rarest_piece_first,
        self.enable_bbs_plus= enable_bbs_plus,
        self.enabel_dht_network=enabel_dht_network

        
        # configure window
        self.title("TorrentX: Advanced peer to peer client")
        self.geometry(f"{1100}x{580}")

        # configure grid layout (4x4)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure((2, 3), weight=0)
        self.grid_rowconfigure((0, 1, 2), weight=1)

        # create sidebar frame with widgets
        self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        
        self.logo_label = customtkinter.CTkLabel(self.sidebar_frame,
                                                 text="Dashboard", 
                                                 font=customtkinter.CTkFont(size=26, weight="bold"),
                                              
                                                 )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        sidebar_button_1_image = customtkinter.CTkImage(light_image=Image.open(os.path.join(self.father_dir, 'test_images/add_user_light.png')),
                                  dark_image=Image.open(os.path.join(self.father_dir, 'test_images/add_user_light.png')),
                                  size=(30, 30))
        
        self.sidebar_button_1 = customtkinter.CTkButton(self.sidebar_frame, 
                                                        command=self.notice_the_torrent_client, 
                                                        text="Download torrent",
                                                        image=sidebar_button_1_image
                                                       )
        
        self.sidebar_button_1.grid(row=1, column=0, padx=20, pady=10)

        mktorrent_image = customtkinter.CTkImage(light_image=Image.open(os.path.join(self.father_dir, 'test_images/home_light.png')),
                                  dark_image=Image.open(os.path.join(self.father_dir, 'test_images/home_dark.png')),
                                  size=(30, 30))
        
        self.sidebar_button_2 = customtkinter.CTkButton(self.sidebar_frame, command=self.maketorrent, text="Make torrent", image=mktorrent_image)
        self.sidebar_button_2.grid(row=2, column=0, padx=20, pady=10)

        self.sidebar_button_5 = customtkinter.CTkButton(self.sidebar_frame, command=self.sidebar_button_event, text="Cancel")
        self.sidebar_button_5.grid(row=3, column=0, padx=20, pady=10)

        logo_image = customtkinter.CTkImage(light_image=Image.open(os.path.join(self.father_dir, 'test_images/CustomTkinter_logo_single.png')),
                                  dark_image=Image.open(os.path.join(self.father_dir, 'test_images/CustomTkinter_logo_single.png')),
                                  size=(50, 50))
        
        self.sidebar_button_6 = customtkinter.CTkLabel(self.sidebar_frame, image=logo_image, text=""
                                                    )
        self.sidebar_button_6.grid(row=4, column=0, padx=20, pady=10)
        

        resume_image = customtkinter.CTkImage(light_image=Image.open(os.path.join(self.father_dir, 'test_images/chat_light.png')),
                                  dark_image=Image.open(os.path.join(self.father_dir, 'test_images/chat_dark.png')),
                                  size=(30, 30))
        
        self.sidebar_button_6 = customtkinter.CTkButton(self.sidebar_frame, command=self.sidebar_button_event, text="Resume", image=resume_image)
        self.sidebar_button_6.grid(row=3, column=0, padx=20, pady=10)


        self.appearance_mode_label = customtkinter.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(self.sidebar_frame, values=["Light", "Dark", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 10))
        self.scaling_label = customtkinter.CTkLabel(self.sidebar_frame, text="UI Scaling:", anchor="w")
        self.scaling_label.grid(row=7, column=0, padx=20, pady=(10, 0))
        self.scaling_optionemenu = customtkinter.CTkOptionMenu(self.sidebar_frame, values=["80%", "90%", "100%", "110%", "120%"],
                                                               command=self.change_scaling_event)
        self.scaling_optionemenu.grid(row=8, column=0, padx=20, pady=(10, 20))

        # create main entry and button
        self.entry = customtkinter.CTkEntry(self,
                                            placeholder_text="Your local torrent path or magnet link here...",
                                            font = customtkinter.CTkFont(size=18, weight="normal", family="Arial"))
        self.entry.grid(row=3, column=1, columnspan=2, padx=(20, 0), pady=(20, 20), sticky="nsew")

        self.main_button_1 = customtkinter.CTkButton(master=self, 
                                                     fg_color="transparent", 
                                                     border_width=2, 
                                                     text_color=("gray10", "#DCE4EE"), 
                                                     text="Torrent it!",
                                                     command=self.notice_the_torrent_client,
                                                     font = customtkinter.CTkFont(size=18, weight="normal", family="Arial"))
        self.main_button_1.grid(row=3, column=3, padx=(20, 20), pady=(20, 20), sticky="nsew")

        # create textbox with scrolloing feature
        #scrollbar = tkinter.Scrollbar(root)
        
        # scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.textbox = customtkinter.CTkTextbox(self, width=250,
                                        font=customtkinter.CTkFont(size=20, weight="normal", family="Times"),
                                        )
        self.ctk_textbox_scrollbar = customtkinter.CTkScrollbar(self, command=self.textbox.yview)
        #self.ctk_textbox_scrollbar.grid(row=0, column=1, sticky="ns")

        self.textbox.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.textbox.insert("0.0", "Logging:")
        self.textbox.configure(yscrollcommand=self.ctk_textbox_scrollbar.set)
        #self.textbox.focus_set()

        # create tabview
        self.tabview = customtkinter.CTkTabview(self, width=250)
        self.tabview.grid(row=0, column=2, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.tabview.add("Extension 1")
        self.tabview.add("Extension 2")
        self.tabview.add("Extension 3")
        self.tabview.tab("Extension 1").grid_columnconfigure(0, weight=1)  # configure grid of individual tabs
        self.tabview.tab("Extension 1").grid_columnconfigure(0, weight=1)

        self.optionmenu_1 = customtkinter.CTkOptionMenu(self.tabview.tab("Extension 1"), dynamic_resizing=False,
                                                        values=["choking", "Optimistic unchoke", "anti-snubbing"])
        self.optionmenu_1.set("choking")
        self.optionmenu_1.grid(row=0, column=0, padx=20, pady=(20, 10))
        combobox_1_str = customtkinter.StringVar(name="Select an option", value="option 2")
        self.combobox_1 = customtkinter.CTkComboBox(self.tabview.tab("Extension 1"),
                                                    values=["choking", "Optimistic unchoke", "anti-snubbing"],
                                                    variable=combobox_1_str,
                                                    )
        ## print(combobox_1_str)
        self.combobox_1.set("choking")
        self.combobox_1.grid(row=1, column=0, padx=20, pady=(10, 10))
        self.string_input_button = customtkinter.CTkButton(self.tabview.tab("Extension 1"), text="Open torrent downloading relevat information",
                                                           command=self.open_torrent_info)
        self.string_input_button.grid(row=2, column=0, padx=20, pady=(10, 10))
        self.label_tab_2 = customtkinter.CTkLabel(self.tabview.tab("Extension 2"), text="rarest-piece-first")
        self.label_tab_2.grid(row=0, column=0, padx=20, pady=20)
        self.label_tab_3 = customtkinter.CTkLabel(self.tabview.tab("Extension 3"), text="end game")
        self.label_tab_3.grid(row=0, column=0, padx=20, pady=20)

        # create radiobutton frame
        self.radiobutton_frame = customtkinter.CTkFrame(self)
        self.radiobutton_frame.grid(row=0, column=3, padx=(20, 20), pady=(20, 0), sticky="nsew")
        self.radio_var = tkinter.IntVar(value=0)
        self.label_radio_group = customtkinter.CTkLabel(master=self.radiobutton_frame, text="End Game Configuration:", font=customtkinter.CTkFont(size=16, weight="bold"))
        self.label_radio_group.grid(row=0, column=2, columnspan=1, padx=10, pady=10, sticky="")
        self.radio_button_1 = customtkinter.CTkRadioButton(master=self.radiobutton_frame, variable=self.radio_var, value=0, text="strategy 1", font = customtkinter.CTkFont(size=14))
        self.radio_button_1.grid(row=1, column=2, pady=10, padx=20, sticky="n")
        self.radio_button_2 = customtkinter.CTkRadioButton(master=self.radiobutton_frame, variable=self.radio_var, value=1, text="strategy 2", font = customtkinter.CTkFont(size=14))
        self.radio_button_2.grid(row=2, column=2, pady=10, padx=20, sticky="n")
        # self.radio_button_3 = customtkinter.CTkRadioButton(master=self.radiobutton_frame, variable=self.radio_var, value=2)
        # self.radio_button_3.grid(row=3, column=2, pady=10, padx=20, sticky="n")

        # create slider and progressbar frame
        self.slider_progressbar_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.slider_progressbar_frame.grid(row=1, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.slider_progressbar_frame.grid_columnconfigure(0, weight=1)
        self.slider_progressbar_frame.grid_rowconfigure(4, weight=1)
        self.seg_button_1 = customtkinter.CTkSegmentedButton(self.slider_progressbar_frame)
        self.seg_button_1.configure(values=["Prorgess bar: pieces", "Progress bar: blocks"])
        self.seg_button_1.set("Prorgess bar: pieces")
        self.seg_button_1.grid(row=0, column=0, padx=(20, 10), pady=(10, 10), sticky="ew")

        self.progressbar_1 = customtkinter.CTkProgressBar(self.slider_progressbar_frame,
                                                          progress_color="#006400",
                                                          fg_color="#d3d3d3")
        self.progressbar_1.grid(row=1, column=0, padx=(20, 10), pady=(10, 10), sticky="ew")
        #self.progressbar_1['maximum'] = 100
        #self.progressbar_1.configure(mode="indeterminate")
        #self.progressbar_1['value'] = 0
        self.progressbar_1.set(0)

        self.progressbar_2 = customtkinter.CTkProgressBar(self.slider_progressbar_frame,
                                                          progress_color="#006400",
                                                          fg_color="#d3d3d3")
        self.progressbar_2.grid(row=2, column=0, padx=(20, 10), pady=(10, 10), sticky="ew")
        self.progressbar_2.set(0)


        self.slider_1 = customtkinter.CTkSlider(self.slider_progressbar_frame, from_=0, to=1, number_of_steps=4)
        self.slider_1.grid(row=3, column=0, padx=(20, 10), pady=(10, 10), sticky="ew")
        self.slider_2 = customtkinter.CTkSlider(self.slider_progressbar_frame, orientation="vertical")
        self.slider_2.grid(row=0, column=1, rowspan=5, padx=(10, 10), pady=(10, 10), sticky="ns")
        self.progressbar_3 = customtkinter.CTkProgressBar(self.slider_progressbar_frame, orientation="vertical")
        self.progressbar_3.grid(row=0, column=2, rowspan=5, padx=(10, 20), pady=(10, 10), sticky="ns")

        # create scrollable frame
        self.scrollable_frame = customtkinter.CTkScrollableFrame(self, label_text="Peer connection")
        self.scrollable_frame.grid(row=1, column=2, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        self.scrollable_frame_switches = []
        # for i in range(1):
        #     switch = customtkinter.CTkSwitch(master=self.scrollable_frame, text="Peer id:{}".format(1))
        #     switch.grid(row=i, column=0, padx=10, pady=(0, 20))
        #     self.scrollable_frame_switches.append(switch)
        

        # create checkbox and switch frame
        self.checkbox_slider_frame = customtkinter.CTkFrame(self)
        # self.checkbox_slider_frame.setvar()
        self.checkbox_slider_frame.grid(row=1, column=3, padx=(20, 20), pady=(20, 0), sticky="nsew")
        self.checkbox_1 = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text="Choking and Optimistic Unchoking")
        self.checkbox_1.grid(row=1, column=0, pady=(20, 0), padx=20, sticky="w")

        self.checkbox_2 = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text="Anti-snubbing")
        self.checkbox_2.grid(row=2, column=0, pady=(20, 0), padx=20, sticky="w")

        self.checkbox_3 = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text="Rarest Piece First")
        self.checkbox_3.grid(row=3, column=0, pady=(20, 0), padx=20, sticky="w")

        self.checkbox_4 = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text="End game")
        self.checkbox_4.grid(row=4, column=0, pady=(20, 0), padx=20, sticky="w")

        self.checkbox_5 = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text="BBs plus")
        self.checkbox_5.grid(row=5, column=0, pady=(20, 0), padx=20, sticky="w")

        self.checkbox_6 = customtkinter.CTkCheckBox(master=self.checkbox_slider_frame, text="DHT network")
        self.checkbox_6.grid(row=6, column=0, pady=(20, 0), padx=20, sticky="w")


        self.appearance_mode_optionemenu.set("Dark")
        self.scaling_optionemenu.set("100%")
        
        self.slider_1.configure(command=self.progressbar_2.set)
        self.slider_2.configure(command=self.progressbar_3.set)

        self.torrent_info_win = None
        self.meta_info = None
        self.tracker_response = None
        self.tracker_info = None
        self.peer_info = []
        self.torrent_client_mode = False
        #self.progressbar_1.configure(mode="indeterminnate")


    def notice_the_torrent_client(self):
        self.torrent_client_mode = True

    def add_peer_switch(self, peer_id, ip_port):
        switch = customtkinter.CTkSwitch(master=self.scrollable_frame, text="Peer id:{}".format(peer_id))
        switch.select()
        switch.grid(row=len(self.scrollable_frame_switches), column=0, padx=10, pady=(0, 20),sticky="w")
        self.scrollable_frame_switches.append(switch)
        self.peer_info.append(App.IP_PORT_ID(ip_port.ip, ip_port.port, peer_id))

    def add_text(self, content):
        self.textbox.insert(index = tkinter.INSERT,
                            text = content,
                            )
        self.textbox.yview_moveto(1.0)


    def open_torrent_info(self):
        #dialog = customtkinter.CTkInputDialog(text="Type in a number:", title="CTkInputDialog")
        #print("CTkInputDialog:", dialog.get_input())
        if self.torrent_info_win is None or not self.torrent_info_win.winfo_exists():
            self.torrent_info_win = ToplevelWindow(
                                                   self.meta_info,
                                                   self.tracker_response,
                                                   self.tracker_info,
                                                   self.peer_info)  # create window if its None or destroyed
        else:
            self.torrent_info_win.focus()  # if window exists focus it

    def change_appearance_mode_event(self, new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)

    def change_scaling_event(self, new_scaling: str):
        new_scaling_float = int(new_scaling.replace("%", "")) / 100
        customtkinter.set_widget_scaling(new_scaling_float)

    def sidebar_button_event(self):
        print("sidebar_button click")


    def maketorrent(self):
        filetypes = (
            ('text files', '*.txt'),
            ('All files', '*.*')
        )

        filename = fd.askopenfilename(
            title='Open a file',
            initialdir='/',
            filetypes=filetypes)
        if not os.path.exists(filename):
            return
        showinfo(
            title='Selected File',
            message=filename
        )
        dialog = customtkinter.CTkInputDialog(text="The name of the torrent", title="Create the name of the torrent")
        torrent_name = dialog.get_input()
        print(filename)
        announce_urls = [ "https://opentracker.i2p.rocks:443/announce",
                            "https://tracker.tamersunion.org:443/announce",
                            "https://tracker.imgoingto.icu:443/announce",
                            "https://tr.burnabyhighstar.com:443/announce",
                            "https://tracker.moeblog.cn:443/announce",
                            "https://tracker.loligirl.cn:443/announce",
                            "https://tracker.lilithraws.org:443/announce",
                            "https://tracker.kuroy.me:443/announce",
                            "https://tr.ready4.icu:443/announce",
                            "https://t1.hloli.org:443/announce",
                            "https://t.zerg.pw/announce",
                            "https://1337.abcvg.info:443/announce"]
        
        information = python_wrapper.main(
            announce_urls = announce_urls, 
            filename_of_the_file_to_be_torrented = filename,
            torrent_name=torrent_name,
            verbose = True
        )

        # showinfo(
        #     title='Make Torrent Thread',
        #     message=information,
        # )

        self.toplevel_window = MakeTorrentThread(message=information)  # create window if its None or destroyed


class MakeTorrentThread(customtkinter.CTkToplevel):
    def __init__(self, message):
        super().__init__()
        self.geometry("800x600")
        self.label = customtkinter.CTkLabel(self, text=message)
        self.label.pack(padx=20, pady=20)


class ToplevelWindow(customtkinter.CTkToplevel):
    def __init__(self, meta_info, tracker_response, tracker_info, peer_info):
        super().__init__()
        self.geometry("600x400")

        # self.label = customtkinter.CTkLabel(self, text="Torrent Downloading Information")
        # self.label.pack(padx=20, pady=20)
        # create tabview
        font=customtkinter.CTkFont(size=14, weight="normal", family="Ubuntu")
        self.tabview = customtkinter.CTkTabview(self, width=560)
        self.tabview.grid(row=0, column=2, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.tabview.add("Torrent")
        self.tabview.add("Tracker")
        self.tabview.add("Peer connection")
        self.tabview.tab("Torrent").grid_columnconfigure(0, weight=1)  # configure grid of individual tabs
        self.tabview.tab("Tracker").grid_columnconfigure(0, weight=1)

        # self.label1_frame = customtkinter.CTkFrame(self, width=560, corner_radius=0)
        self.label_tab_1_1 = customtkinter.CTkLabel(self.tabview.tab("Torrent"), 
                                                    text="Annouce: {}".format(meta_info[b'announce'].decode('utf-8'))
                                                    , font = font
                                                    , anchor="w"
                                                    ,width = 520
                                                    )
        self.label_tab_1_1.grid(row=0, column=0, padx=20, pady=2)
        self.label_tab_1_2 = customtkinter.CTkLabel(self.tabview.tab("Torrent"), 
                                                    text="Comment: {}".format(meta_info[b'comment'].decode('utf-8'))
                                                    , font = font
                                                    , anchor="w"
                                                    ,width = 520
                                                    )
        self.label_tab_1_2.grid(row=1, column=0, padx=20, pady=2)
        self.label_tab_1_3 = customtkinter.CTkLabel(self.tabview.tab("Torrent"), 
                                                    text="Created by: {}".format(meta_info[b'created by'].decode('utf-8'))
                                                    , font = font
                                                    , anchor="w"
                                                    ,width = 520
                                                    )
        self.label_tab_1_3.grid(row=2, column=0, padx=20, pady=2)
        timestamp = meta_info[b'creation date']  # Replace with your timestamp
        time_tuple = time.gmtime(timestamp)
        asctime_time = time.asctime(time_tuple)
        self.label_tab_1_4 = customtkinter.CTkLabel(self.tabview.tab("Torrent"), 
                                                    text="Creation Date: {}".format(asctime_time)
                                                    , font = font
                                                    , anchor="w"
                                                    ,width = 520
                                                    )
        self.label_tab_1_4.grid(row=3, column=0, padx=20, pady=2)
        self.label_tab_1_5 = customtkinter.CTkLabel(self.tabview.tab("Torrent"), 
                                                    text="File name: {}".format(meta_info[b'info'][b'name'].decode('utf-8'))
                                                    , font = font
                                                    , anchor="w"
                                                    ,width = 520
                                                    )
        self.label_tab_1_5.grid(row=4, column=0, padx=20, pady=2)
        self.label_tab_1_6 = customtkinter.CTkLabel(self.tabview.tab("Torrent"), 
                                                    text="File length: {}".format(meta_info[b'info'][b'length'])
                                                    , font = font
                                                    , anchor="w"
                                                    ,width = 520
                                                    )
        self.label_tab_1_6.grid(row=5, column=0, padx=20, pady=2)
        self.label_tab_1_7 = customtkinter.CTkLabel(self.tabview.tab("Torrent"), 
                                                    text="Piece length: {}".format(meta_info[b'info'][b'piece length'])
                                                    , font = font, 
                                                    anchor="w"
                                                    ,width = 520
                                                    )
        self.label_tab_1_7.grid(row=6, column=0, padx=20, pady=2)




        self.label_tab_2_1 = customtkinter.CTkLabel(self.tabview.tab("Tracker")
                                                    , text="Leechers (Incomplete torrent holder): {}".format(tracker_response.incomplete)
                                                    , font = font
                                                    , anchor="w"
                                                    ,width = 520
                                                    )
        self.label_tab_2_1.grid(row=0, column=0, padx=20, pady=2)
        self.label_tab_2_2 = customtkinter.CTkLabel(self.tabview.tab("Tracker")
                                                    , text="Seeders (Complete torrent holder): {}".format(tracker_response.complete)
                                                    , font = font
                                                    , anchor="w"
                                                    ,width = 520
                                                    )
        self.label_tab_2_2.grid(row=1, column=0, padx=20, pady=2)
        self.label_tab_2_3 = customtkinter.CTkLabel(self.tabview.tab("Tracker")
                                                    , text="Tracker query interval: {}".format(tracker_response.interval)
                                                    , font = font
                                                    , anchor="w"
                                                    ,width = 520
                                                    )
        self.label_tab_2_3.grid(row=2, column=0, padx=20, pady=2)
        # self.label_tab_2_4 = customtkinter.CTkLabel(self.tabview.tab("Tracker")
        #                                             , text="Peers: {}".format(",".join([x for (x, _) in tracker_response.peers]))
        #                                             , font = font
        #                                             , anchor="w")
        # self.label_tab_2_4.grid(row=3, column=0, padx=20, pady=2)
        self.label_tab_2_5 = customtkinter.CTkLabel(self.tabview.tab("Tracker")
                                                    , text="Announce URL: {}".format(tracker_info.announce),
                                                      font = font,
                                                      anchor="w"
                                                      ,width = 520
                                                      )
        self.label_tab_2_5.grid(row=3, column=0, padx=20, pady=2)
        if tracker_info.announce_list is not None and len(tracker_info) >= 1:
            self.label_tab_2_6 = customtkinter.CTkLabel(self.tabview.tab("Tracker")
                                                        , text="Announce list: {}".format(",\n ".join([x for (x, _) in tracker_info.announce_list]))
                                                        , font = font
                                                        , anchor="w"
                                                        ,width = 520
                                                        )
            self.label_tab_2_6.grid(row=4, column=0, padx=20, pady=2)



        self.label_tab_3 = []
        
        for i in range(len(peer_info)):
            self.label_tab_tmp = customtkinter.CTkLabel(self.tabview.tab("Peer connection"), text="Peer id: {} Peer ip:{} Peer Port: {}\n"
                                                        .format(peer_info[i].id, peer_info[i].ip, peer_info[i].port)
                                                        , font = font
                                                        , anchor="w"
                                                        ,width = 520
                                                        )
            self.label_tab_tmp.grid(row=i, column=0, padx=20, pady=2)
            self.label_tab_3.append(self.label_tab_tmp)

if __name__ == "__main__":
    app = App()
    app.mainloop()
