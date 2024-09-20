###############################################
# DONT CHANGE # These are base imports needed #
###############################################
import glob
import os
import sys
import json
import time
import torch
import logging
from pathlib import Path
from fastapi import (HTTPException)
logging.disable(logging.WARNING)
###############################################
# DONT CHANGE # Get Pytorch & Python versions #
###############################################
pytorch_version = torch.__version__
cuda_version = torch.version.cuda
major, minor, micro = sys.version_info[:3]
python_version = f"{major}.{minor}.{micro}"
try:
    import deepspeed
    deepspeed_available = True
except ImportError:
    deepspeed_available = False
    pass

#############################################################################################################
#############################################################################################################
# CHANGE ME # Run any specifc imports, requirements or setup any global vaiables needed for this TTS Engine #
#############################################################################################################
#############################################################################################################
# In this section you will import any imports that your specific TTS Engine will use. You will provide any
# start-up errors for those bits, as if you were starting up a normal Python script. Note the logging.disable
# a few lines up from here, you may want to # that out while debugging!
try:
    import torchaudio
    import wave
    import io
    import random
    import numpy as np
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import Xtts
    from TTS.api import TTS
    from TTS.utils.synthesizer import Synthesizer
except ModuleNotFoundError:
    print(
        f"[Startup] \033[91mWarning\033[0m Could not find the TTS module. Make sure to install the requirements for the alltalk_tts extension.",
        f"[Startup] \033[91mWarning\033[0m Linux / Mac:\npip install -r extensions/alltalk_tts/requirements.txt\n",
        f"[Startup] \033[91mWarning\033[0m Windows:\npip install -r extensions\\alltalk_tts\\requirements.txt\n",
        f"[Startup] \033[91mWarning\033[0m If you used the one-click installer, paste the command above in the terminal window launched after running the cmd_ script. On Windows, that's cmd_windows.bat."
    )
    raise

#############################################################
# DONT CHANGE # Do not change the Class name from tts_class #
#############################################################
class tts_class:
    def __init__(self):
        ########################################################################
        # DONT CHANGE # Sets up the base variables required for any tts engine #
        ########################################################################
        self.branding = None                                                    
        self.this_dir = Path(__file__).parent.resolve()                         # Sets up self.this_dir as a variable for the folder THIS script is running in.
        self.main_dir = Path(__file__).parent.parent.parent.parent.resolve()    # Sets up self.main_dir as a variable for the folder AllTalk is running in
        self.device = "cuda" if torch.cuda.is_available() else "cpu"            # Sets up self.device to cuda if torch exists with Nvidia/CUDA, otherwise sets to cpu
        self.cuda_is_available = torch.cuda.is_available()                      # Sets up cuda_is_available as a True/False to track if Nvidia/CUDA was found on the system
        self.tts_generating_lock = False                                        # Used to lock and unlock the tts generation process at the start/end of tts generation. 
        self.tts_stop_generation = False                                        # Used in conjunction with tts_generating_lock to call for a stop to the current generation. If called (set True) it needs to be set back to False when generation has been stopped.
        self.tts_narrator_generatingtts = False                                 # Used to track if the current tts processes is narrator based. This can be used in conjunction with lowvram and device to avoid moving model between GPU(CUDA)<>RAM(CPU) each chunk of narrated text generated.
        self.model = None                                                       # If loading a model into CUDA/VRAM/RAM "model" is used as the variable name to load and interact with (see the XTTS model_engine script for examples.)
        self.is_tts_model_loaded = False                                        # Used to track if a model is actually loaded in and error/fail things like TTS generation if its False
        self.current_model_loaded = None                                        # Stores the name of the currenly loaded in model
        self.available_models = None                                            # List of available models found by "def scan_models_folder"
        self.setup_has_run = False                                              # Tracks if async def setup(self) has run, by setting to True, so that the /api/ready endpoint can provide a "Ready" status
        ##############################################################################################
        # DONT CHANGE # Load in a list of the available TTS engines and the currently set TTS engine #
        ##############################################################################################
        tts_engines_file = os.path.join(self.main_dir, "system", "tts_engines", "tts_engines.json")
        with open(tts_engines_file, "r") as f:
            tts_engines_data = json.load(f)
        self.engines_available = [engine["name"] for engine in tts_engines_data["engines_available"]]       # A list of ALL the TTS engines available to be loaded by AllTalk
        self.engine_loaded = tts_engines_data["engine_loaded"]                                              # In "tts_engines.json" what is the currently set TTS engine loading into AllTalk
        self.selected_model = tts_engines_data["selected_model"]                                            # In "tts_engines.json" what is the currently set TTS model loading into AllTalk
        ############################################################################
        # DONT CHANGE # Pull out all the settings for the currently set TTS engine #
        ############################################################################
        with open(os.path.join(self.this_dir, "model_settings.json"), "r") as f:
            tts_model_loaded = json.load(f)
        # Access the model details
        self.manufacturer_name = tts_model_loaded["model_details"]["manufacturer_name"]                     # The company/person/body that generated the TTS engine/models etc
        self.manufacturer_website = tts_model_loaded["model_details"]["manufacturer_website"]               # The website of the company/person/body where people can find more information
        # Access the features the model is capable of:
        self.audio_format = tts_model_loaded["model_capabilties"]["audio_format"]                           # This details the audio format your TTS engine is set to generate TTS in e.g. wav, mp3, flac, opus, acc, pcm. Please use only 1x format.
        self.deepspeed_capable = tts_model_loaded["model_capabilties"]["deepspeed_capable"]                 # Is your model capable of DeepSpeed
        self.deepspeed_available = 'deepspeed' in globals()                                                 # When we did the import earlier, at the top of this script, was DeepSpeed available for use
        self.generationspeed_capable = tts_model_loaded["model_capabilties"]["generationspeed_capable"]     # Does this TTS engine support changing the speed of the generated TTS
        self.languages_capable = tts_model_loaded["model_capabilties"]["languages_capable"]                 # Are the actual models themselves capable of generating in multiple languages OR is each model language specific
        self.lowvram_capable = tts_model_loaded["model_capabilties"]["lowvram_capable"]                     # Is this engine capable of using low VRAM (moving the model between CPU And GPU memory)
        self.multimodel_capable = tts_model_loaded["model_capabilties"]["multimodel_capable"]               # Is there just the one model or are there multiple models this engine supports.
        self.repetitionpenalty_capable = tts_model_loaded["model_capabilties"]["repetitionpenalty_capable"] # Is this TTS engine capable of changing the repititon penalty
        self.streaming_capable = tts_model_loaded["model_capabilties"]["streaming_capable"]                 # Is this TTS engine capabale of generating streaming audio
        self.temperature_capable = tts_model_loaded["model_capabilties"]["temperature_capable"]             # Is this TTS engine capable of changing the temperature of the models
        self.multivoice_capable = tts_model_loaded["model_capabilties"]["multivoice_capable"]               # Are the models multi-voice or single vocice models
        self.pitch_capable = tts_model_loaded["model_capabilties"]["pitch_capable"]                         # Is this TTS engine capable of changing the pitch of the genrated TTS
        # Access the current enginesettings
        self.def_character_voice = tts_model_loaded["settings"]["def_character_voice"]                      # What is the current default main/character voice that will be used if no voice specified.
        self.def_narrator_voice = tts_model_loaded["settings"]["def_narrator_voice"]                        # What is the current default narrator voice that will be used if no voice specified.
        self.deepspeed_enabled = tts_model_loaded["settings"]["deepspeed_enabled"]                          # If its available, is DeepSpeed enabled for the TTS engine
        self.engine_installed = tts_model_loaded["settings"]["engine_installed"]                            # Has the TTS engine been setup/installed (not curently used)
        self.generationspeed_set = tts_model_loaded["settings"]["generationspeed_set"]                      # What is the set/stored speed for generation.
        self.lowvram_enabled = tts_model_loaded["settings"]["lowvram_enabled"]                              # If its available, is LowVRAM enabled for the TTS engine
        # Check if someone has enabled lowvram on a system that's not CUDA enabled
        self.lowvram_enabled = False if not torch.cuda.is_available() else self.lowvram_enabled             # If LowVRAM is mistakenly set and CUDA is not available, this will force it back off
        self.repetitionpenalty_set = tts_model_loaded["settings"]["repetitionpenalty_set"]                  # What is the currenly set repitition policy of the model (If it support repetition)
        self.temperature_set = tts_model_loaded["settings"]["temperature_set"]                              # What is the currenly set temperature of the model (If it support temp)
        self.pitch_set = tts_model_loaded["settings"]["pitch_set"]                                          # What is the currenly set pitch of the model (If it support temp)
        # Gather the OpenAI API Voice Mappings
        self.openai_alloy = tts_model_loaded["openai_voices"]["alloy"]                                      # The TTS engine voice that will be mapped to Open AI Alloy voice
        self.openai_echo = tts_model_loaded["openai_voices"]["echo"]                                        # The TTS engine voice that will be mapped to Open AI Echo voice
        self.openai_fable = tts_model_loaded["openai_voices"]["fable"]                                      # The TTS engine voice that will be mapped to Open AI Fable voice
        self.openai_nova = tts_model_loaded["openai_voices"]["nova"]                                        # The TTS engine voice that will be mapped to Open AI Nova voice
        self.openai_onyx = tts_model_loaded["openai_voices"]["onyx"]                                        # The TTS engine voice that will be mapped to Open AI Onyx voice
        self.openai_shimmer = tts_model_loaded["openai_voices"]["shimmer"]                                  # The TTS engine voice that will be mapped to Open AI Shimmer voice  
        ###################################################################
        # DONT CHANGE #  Load params and api_defaults from confignew.json #
        ###################################################################
        # Define the path to the confignew.json file
        configfile_path = self.main_dir / "confignew.json"
        # Load config file and get settings
        with open(configfile_path, "r") as configfile:
            configfile_data = json.load(configfile)
        self.branding = configfile_data.get("branding", "")                                                 # Sets up self.branding for outputting the name stored in the "confgnew.json" file, as used in print statements.
        self.params = configfile_data                                                                       # Loads in the curent "confgnew.json" file to self.params.
        self.debug_tts = configfile_data.get("debugging").get("debug_tts")                                  # Can be used within this script as a True/False flag for generally debugging the TTS generation process. 
        self.debug_tts_variables = configfile_data.get("debugging").get("debug_tts_variables")              # Can be used within this script as a True/False flag for generally debugging variables (if you wish).      
    ################################################################
    # DONT CHANGE #  Print out Python, CUDA, DeepSpeed versions ####
    ################################################################
    def printout_versions(self):
        if deepspeed_available:
            print(f"[{self.branding}ENG] \033[92mDeepSpeed version :\033[93m",deepspeed.__version__,"\033[0m")
        else:
            print(f"[{self.branding}ENG] \033[92mDeepSpeed version :\033[93m Not available\033[0m")
        print(f"[{self.branding}ENG] \033[92mPython Version    :\033[93m {python_version}\033[0m")
        print(f"[{self.branding}ENG] \033[92mPyTorch Version   :\033[93m {pytorch_version}\033[0m")
        if cuda_version is None:
            print(f"[{self.branding}ENG] \033[92mCUDA Version      :\033[91m Not available\033[0m")
        else:
            print(f"[{self.branding}ENG] \033[92mCUDA Version      :\033[93m {cuda_version}\033[0m")
        print(f"[{self.branding}ENG]")
        return

    ###################################################################################      
    ###################################################################################
    # CHANGE ME # Inital setup of the model and engine. Called when the script starts #
    ###################################################################################
    ###################################################################################
    # In here you will add code to load in your model and do its inital setup. So you
    # may be calling your model loader via handle_tts_method_change or if your TTS
    # engine doesnt actually load a model into CUDA or System RAM, you may be doing 
    # Something to fake its start-up.
    async def setup(self):
        self.printout_versions()
        self.available_models = self.scan_models_folder()
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        # ↑↑↑ Keep everything above this line ↑↑↑
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        
        if self.selected_model:
            tts_model = f"{self.selected_model}"
            if tts_model in self.available_models:
                await self.handle_tts_method_change(tts_model)
                self.current_model_loaded = tts_model
                
            # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
            # ↓↓↓ Keep everything below this line ↓↓↓
            # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓                  
            else:
                self.current_model_loaded = "No Models Available"
                print(f"[{self.branding}ENG] \033[91mError\033[0m: Selected model '{self.selected_model}' not found in the models folder.")
        self.setup_has_run = True  # Set to True, so that the /api/ready endpoint can provide a "Ready" status                   

    ##################################
    ##################################
    # CHANGE ME #  Low VRAM Swapping #
    ##################################
    ##################################
    # If your model does load into CUDA and you want to support LowVRAM, aka moving the model
    # on the fly between CUDA and System RAM on each generation request, you will be adding
    # The code in here to do it. See the XTTS tts engine for an example. Piper however, doesnt
    # Load into VRAM or System RAM, also low vram is set globally disabled by the model_settings.JSON
    # file, so this would never get called anywyay, however, we still need to keep an empty 
    # function in place. Piper TTS uses "pass" telling function to just exit out cleanly if called.
    # However, its quite a simple check along the lines of "if CUDA is available and model is
    # in X place, then send it to Y place (or Y to X).
    async def handle_lowvram_change(self):
        if torch.cuda.is_available():
            if self.device == "cuda":
                self.device = "cpu"
                self.model.to(self.device)
                torch.cuda.empty_cache()
            else:
                self.device == "cpu"
                self.device = "cuda"
                self.model.to(self.device)
                
    ########################################
    ########################################
    # CHANGE ME #  DeepSpeed model loading #
    ########################################
    ########################################
    # If the model supports CUDA and DeepSpeed, this is where you can handle re-loading
    # the model as/when DeepSpeed is enabled/selected in the user interface. If your 
    # TTS model doesnt support DeepSpeed, then it should be globally set in your
    # model_settings.JSON and this function will never get called, however it still needs
    # to exist as a function.
    async def handle_deepspeed_change(self, value):
        if value:
            # DeepSpeed enabled
            print(f"[{self.branding}ENG] \033[93mDeepSpeed Activating\033[0m")
            await self.unload_model()
            self.params["tts_method_api_local"] = False
            self.params["tts_method_xtts_local"] = True
            self.deepspeed_enabled = True
            await self.setup()
        else:
            # DeepSpeed disabled
            print(f"[{self.branding}ENG] \033[93mDeepSpeed De-Activating\033[0m")
            self.deepspeed_enabled = False
            await self.unload_model()
            await self.setup()
        return value  # Return new checkbox value
    
    ##############################################################################################################################################
    ##############################################################################################################################################
    # CHANGE ME # scan for available models/voices that are relevant to this TTS engine # XTTS is very unusal as it has 2x model loading methods #
    ##############################################################################################################################################
    ##############################################################################################################################################
    # This function looks and reports back the list of possible models your TTS engine can
    # load in. Some TTS engines have multiple models they can load and you will want to use
    # code for checking if the models are in the correct location/placement within the disk
    # the correct files exst per model etc (check XTTS for an example of this). Some models
    # like Piper, the actual models are the voices, so in the Piper scan_models_folder
    # function, we fake the only model being available as {'piper': 'piper'} aka, model name
    # then engine name, then we use the voices_file_list to populate the models as available
    # voices that can be selected in the interface.    
    # If no models are found, we return "No Models Available" and continue on with the script.
    def scan_models_folder(self):
        models_folder = self.main_dir / "models" / "xtts" # Edit to match the name of your folder where voices are stored
        self.available_models = {}
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        # ↑↑↑ Keep everything above this line ↑↑↑
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑  
            
        required_files = ["config.json", "model.pth", "mel_stats.pth", "speakers_xtts.pth", "vocab.json", "dvae.pth"]
        for subfolder in models_folder.iterdir():
            if subfolder.is_dir():
                model_name = subfolder.name
                if all(subfolder.joinpath(file).exists() for file in required_files):
                    self.available_models[f"xtts - {model_name}"] = "xtts"
                    self.available_models[f"apitts - {model_name}"] = "apitts"
                    
                # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
                # ↓↓↓ Keep everything below this line ↓↓↓
                # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓  
                else:
                    self.available_models = {'No Models Available': 'xtts'} # Edit the xtts to whatever the name of your engine is
                    print(f"[{self.branding}ENG] \033[91mWarning\033[0m: Model folder '{model_name}' is missing required")
                    print(f"[{self.branding}ENG] \033[91mWarning\033[0m: files or the folder does not exist.")                   
        return self.available_models

    #############################################################
    #############################################################
    # CHANGE ME #  POPULATE FILES LIST FROM VOICES DIRECTORY ####
    #############################################################
    #############################################################
    # This function looks and reports back the list of possible voice your TTS engine can
    # load in. Some TTS engines the voices are wav file samples (XTTS), some are models 
    # (Piper) and some are text (Parler) thats stored in a JSON file. We just need to 
    # populate the "voices" variable somehow and if no voices are found, we return
    # "No Voices Found" back to the interface/api.    
    def voices_file_list(self):
        try:
            voices = []
            # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
            # ↑↑↑ Keep everything above this line ↑↑↑
            # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                 
            directory = self.main_dir / "voices"
            # Step 1: Add .wav files in the main "voices" directory to the list
            voices.extend([f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and f.endswith(".wav")])
            
            # Step 2: Walk through subfolders and add subfolder names if they contain .wav files
            for root, dirs, files in os.walk(directory):
                # Skip the root directory itself and only consider subfolders
                if os.path.normpath(root) != os.path.normpath(directory):
                    if any(f.endswith(".wav") for f in files):
                        folder_name = os.path.basename(root) + "/"
                        voices.append(folder_name)
            
            # Remove "voices/" from the list if it somehow got added
            voices = [v for v in voices if v != "voices/"]
            
            # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
            # ↓↓↓ Keep everything below this line ↓↓↓
            # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓                     
            if not voices:
                return ["No Voices Found"] # Return a list with {'No Voices Found'} if there are no voices/voice models.
            return voices # Return a list of models in the format {'engine name': 'model 1', 'engine name': 'model 2", etc}
        except Exception as e:
            print(f"[{self.branding}ENG] \033[91mError\033[0m: Voices/Voice Models not found. Cannot load a list of voices.")
            print(f"[{self.branding}ENG]")
            return ["No Voices Found"]

    ######################################################################################
    ######################################################################################
    # CHANGE ME # Model loading # XTTS is very unusal as it has 2x model loading methods #
    ######################################################################################
    ######################################################################################
    # This function will handle the loading of your model, into VRAM/CUDA, System RAM or whatever.
    # In XTTS, which has 2x model loader types, there are 2x loaders. They are called by "def handle_tts_method_change"
    # In Piper we fake a model loader as Piper doesnt actually load a model into CUDA/System RAM as such. So, in that
    # situation, api_manual_load_model is kind of a blank function. Though we do set self.is_tts_model_loaded = True
    # as this is used elsewhere in the scripts to confirm that a model is available to be used for TTS generation.
    # We always check for "No Models Available" being sent as that means we are trying to load in a model that 
    # doesnt exist/wasnt found on script start-up e.g. someone deleted the model from the folder or something.
    
    # Model loader Method 1
    async def api_manual_load_model(self, model_name):
        if "No Models Available" in self.available_models:
            print(f"[{self.branding}ENG] \033[91mError\033[0m: No models for this TTS engine were found to load. Please download a model.")
            return
        model_path = self.main_dir / "models" / "xtts" / model_name
        print("model_path is:", model_path) if self.debug_tts_variables else None
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        # ↑↑↑ Keep everything above this line ↑↑↑
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑        
        
        self.model = TTS(   # self.model is a global variable for the variable controlling the model in vram/cuda/system ram
            model_path=model_path,
            config_path=model_path / "config.json",
        ).to(self.device)
        print(f"[{self.branding}ENG] \033[94mModel License:\033[93m https://coqui.ai/cpml.txt\033[0m")
        
        # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        # ↓↓↓ Keep everything below this line ↓↓↓
        # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        self.is_tts_model_loaded = True
        return self.model

    # Model loader Method 2
    async def xtts_manual_load_model(self, model_name):
        if "No Models Available" in self.available_models:
            print(f"[{self.branding}ENG] \033[91mError\033[0m: No models for this TTS engine were found to load. Please download a model.")
            return
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        # ↑↑↑ Keep everything above this line ↑↑↑
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑       
        
        config = XttsConfig()
        model_path = self.main_dir / "models" / "xtts" / model_name
        config_path = model_path / "config.json"
        vocab_path_dir = model_path / "vocab.json"
        checkpoint_dir = model_path
        config.load_json(str(config_path))
        self.model = Xtts.init_from_config(config)
        self.model.load_checkpoint(
            config,
            checkpoint_dir=str(checkpoint_dir),
            vocab_path=str(vocab_path_dir),
            use_deepspeed=self.deepspeed_enabled,
        )
        self.model.to(self.device)
        self.is_tts_model_loaded = True
        print(f"[{self.branding}ENG] \033[94mModel License:\033[93m https://coqui.ai/cpml.txt\033[0m")
        
        # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        # ↓↓↓ Keep everything below this line ↓↓↓
        # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓        
        return self.model
    
    ###############################
    ###############################
    # CHANGE ME # Model unloading #
    ###############################
    ###############################
    # This function will handle the UN-loading of your model, from VRAM/CUDA, System RAM or whatever.
    # In XTTS, that model loads into CUDA/System Ram, so when we swap models, we want to unload the current model
    # free up the memory and then load in the new model to VRAM/CUDA. On the flip side of that, Piper doesnt
    # doesnt load into memory, so we just need to put a fake function here that doesnt really do anything
    # other than set "self.is_tts_model_loaded = False", which would be set back to true by the model loader. 
    # So look at the Piper model_engine.py if you DONT need to unload models.       
    async def unload_model(self):
        self.is_tts_model_loaded = False
        if not self.current_model_loaded == None:
            print(f"[{self.branding}ENG] \033[94mUnloading model \033[0m") if self.debug_tts else None
        if hasattr(self, 'model'):
            del self.model            
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return None
    
    ###################################################################################################################################    
    ###################################################################################################################################
    # CHANGE ME # Model changing. Unload out old model and load in a new one # XTTS is very unusal as it has 2x model loading methods #
    ###################################################################################################################################
    ###################################################################################################################################
    # This function is your central model loading/unloading handler that deals with the above functions as necesary, to call loading, unloading,
    # swappng DeepSpeed, Low vram etc. This function gets called with a "engine name - model name" type call. In XTTS, because there are 2x
    # model loader types, (XTTS and APILocal), we take tts_method and split the "engine name - model name" into a loader type and the model
    # that it needs to load in and then we call the correct loader function. Whereas in Piper, which doesnt load models into memory at all, 
    # we just have a fake function that doesnt really do anything. We always check to see if the model name has "No Models Available" in the
    # name thats sent over, just to catch any potential errors. We display the start load time and end load time. Thats about it.
    async def handle_tts_method_change(self, tts_method):
        generate_start_time = time.time() # Record the start time of loading the model
        if "No Models Available" in self.available_models:
            print(f"[{self.branding}ENG] \033[91mError\033[0m: No models for this TTS engine were found to load. Please download a model.")
            return False
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        # ↑↑↑ Keep everything above this line ↑↑↑
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        
        await self.unload_model()
        if tts_method.startswith("xtts"):
            model_name = tts_method.split(" - ")[1]
            print(f"[{self.branding}ENG]\033[94m Model/Engine :\033[93m {model_name}\033[94m loading into\033[93m", self.device,"\033[0m")
            self.model = await self.xtts_manual_load_model(model_name)
            self.current_model_loaded = f"xtts - {model_name}"
        elif tts_method.startswith("apitts"):
            model_name = tts_method.split(" - ")[1]
            print(f"[{self.branding}ENG]\033[94m Model/Engine :\033[93m {model_name}\033[94m loading into\033[93m", self.device,"\033[0m")
            self.model = await self.api_manual_load_model(model_name)
            self.current_model_loaded = f"apitts - {model_name}"
        else:
            self.current_model_loaded = None
            return False

        # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        # ↓↓↓ Keep everything below this line ↓↓↓
        # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓ 
        generate_end_time = time.time() # Create an end timer for calculating load times
        generate_elapsed_time = generate_end_time - generate_start_time  # Calculate start time minus end time
        print(f"[{self.branding}ENG] \033[94mLoad time :\033[93m {generate_elapsed_time:.2f} seconds.\033[0m") # Print out the result of the load time
        return True

    ##########################################################################################################################################    
    ##########################################################################################################################################
    # CHANGE ME # Model changing. Unload out old model and load in a new one # XTTS is very unusal as it has 2x model TTS generation methods #
    ##########################################################################################################################################
    ##########################################################################################################################################
    # In here all the possible options are sent over (text, voice to use, lanugage, speed etc etc) and its up to you how you use them, or not.
    # obviously if your TTS engine doesnt support speed for example, generationspeed_capable should be set False in your model_settings.JSON file
    # and a fake "generationspeed_set" value should be set. This allows a fake value to be sent over from the main script, even though it
    # wouldnt actually ever be used in the generation below. Nonethless all these values, real or just whats inside the configuration file
    # will be sent over for use. 
    # Setting the xxxxxxx_capabale in the model_settings.JSON file, will enable/disable them being selectable by the user. For example, if you
    # set "generationspeed_capable" as false in the model_settings.JSON file, a user will not be able to select OR set the setting for 
    # generation speed.
    # One thing to note is that we HAVE to have something in this generation request that is synchronous from the way its called, which means
    # we have to have an option for Streaming, even if our TTS engine doesnt support streaming. So in that case, we would set streaming_capable
    # as false in our model_settings.JSON file, meaning streaming will never be called. However, we have to put a fake streaming routine in our
    # function below (or a real function if it does support streaming of course). Parler has an example of a fake streaming function, which is
    # very clearly highlighted in its model_engine.py script.
    # Piper TTS, which uses command line based calls and therefore has different ones for Windows and Linux/Mac, has an example of doing this
    # within its model_engine.py file.   
    async def generate_tts(self, text, voice, language, temperature, repetition_penalty, speed, pitch, output_file, streaming):
        print(f"[{self.branding}Debug] Entered model_engine.py generate_tts function") if self.debug_tts else None
        if not self.is_tts_model_loaded: # Check if a model is loaded and error out if not.
            error_message = f"[{self.branding}ENG] \033[91mError\033[0m: You currently have no TTS model loaded." 
            print(error_message)
            raise HTTPException(status_code=400, detail="You currently have no TTS model loaded.")  # Raise an exception with a meaningful HTTP status code
        self.tts_generating_lock = True # Set the tts_generating lock to True, which stops other generation requests being sent into the pipeline
        print(f"[{self.branding}Debug] Checking low VRAM") if self.debug_tts else None
        if self.lowvram_enabled and self.device == "cpu": # If necessary, move the model out of System Ram to VRAM
            print(f"[{self.branding}Debug] Switching device") if self.debug_tts else None
            await self.handle_lowvram_change()
        print(f"[{self.branding}Debug] Setting a generate time") if self.debug_tts else None
        generate_start_time = time.time()  # Record the start time of generating TTS
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        # ↑↑↑ Keep everything above this line ↑↑↑
        # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑

        # XTTSv2 LOCAL & Xttsv2 FT Method
        print(f"[{self.branding}Debug] Deciding if streaming or not") if self.debug_tts else None
        print(f"[{self.branding}Debug] self.current_model_loaded is:", self.current_model_loaded) if self.debug_tts else None
        self.current_model_loaded
        print(f"[{self.branding}Debug] Audio Sample Detection") if self.debug_tts else None
        print(f"[{self.branding}Debug] Voice name sent in request is:", voice) if self.debug_tts else None
        # Check if the voice ends with a slash, indicating it's a directory
        if voice.endswith("/") or voice.endswith("\\"):
            # Remove the trailing slash for proper path detection
            voice = voice.rstrip("/\\")
        if os.path.isdir(os.path.join(self.main_dir, "voices", voice)):
            # Normalize the path for the directory and then search for .wav files
            normalized_path = os.path.normpath(os.path.join(self.main_dir, "voices", voice))
            wavs_files = glob.glob(os.path.join(normalized_path, "*.wav"))
            print(f"[{self.branding}Debug] Directory of multiple voice samples detected. Using multiple WAV files:", wavs_files) if self.debug_tts else None            
            # If there are more than 5 .wav files, randomly select 5
            if len(wavs_files) > 5:
                wavs_files = random.sample(wavs_files, 5)
                print(f"[{self.branding}Debug] More than 5 wav files detected so only using 5x random audio samples:", wavs_files) if self.debug_tts else None
        else:
            # Normalize the path for the file
            normalized_path = os.path.normpath(os.path.join(self.main_dir, "voices", voice))
            wavs_files = [normalized_path]
            print(f"[{self.branding}Debug] Single voice sample detected. Using one WAV sample:", wavs_files) if self.debug_tts else None

        if self.current_model_loaded.startswith ("xtts"):
            print(f"[{self.branding}Debug] Text arriving at TTS engine is: {text}") if self.debug_tts else None
            gpt_cond_latent, speaker_embedding = self.model.get_conditioning_latents(
                audio_path=wavs_files,
                gpt_cond_len=self.model.config.gpt_cond_len,
                max_ref_length=self.model.config.max_ref_len,
                sound_norm_refs=self.model.config.sound_norm_refs,
            )
            print(f"[{self.branding}Debug] Moving to common args") if self.debug_tts else None
            # Common arguments for both functions
            common_args = {
                "text": text,
                "language": language,
                "gpt_cond_latent": gpt_cond_latent,
                "speaker_embedding": speaker_embedding,
                "temperature": float(temperature),
                "length_penalty": float(self.model.config.length_penalty),
                "repetition_penalty": float(repetition_penalty),
                "top_k": int(self.model.config.top_k),
                "top_p": float(self.model.config.top_p),
                "speed": float(speed),
                "enable_text_splitting": True
            }
            print(f"[{self.branding}Debug] Common arguments: {common_args}") if self.debug_tts_variables else None
            #tts_stop_generation = False # Called to stop generation of the current text at whatever stage its at. currently only set for streaming.
            # Determine the correct inference function and add streaming specific argument if needed
            inference_func = self.model.inference_stream if streaming else self.model.inference
            if streaming:
                common_args["stream_chunk_size"] = 20

            # Call the appropriate function
            output = inference_func(**common_args)

            # Process the output based on streaming or non-streaming
            if streaming:
                print(f"[{self.branding}Debug] Streaming audio generation started") if self.debug_tts else None
                # Streaming-specific operations
                file_chunks = []
                wav_buf = io.BytesIO()
                with wave.open(wav_buf, "wb") as vfout:
                    vfout.setnchannels(1)
                    vfout.setsampwidth(2)
                    vfout.setframerate(24000)
                    vfout.writeframes(b"")
                wav_buf.seek(0)
                yield wav_buf.read()

                for i, chunk in enumerate(output):
                    if self.tts_stop_generation: # This is the variable that is called by the stop generation endpoint and interrupts streaming chunk generation when set True.
                        print(f"[{self.branding}GEN] Stopping audio generation.") if self.debug_tts else None
                        file_chunks.clear()  # Clear the file_chunks list
                        self.tts_stop_generation = False # Set the stop back to false
                        self.tts_generating_lock = False # Undo the generation lock
                        break # Exit out of the function
                    file_chunks.append(chunk)
                    if isinstance(chunk, list):
                        chunk = torch.cat(chunk, dim=0)
                    chunk = chunk.clone().detach().cpu().numpy()
                    chunk = chunk[None, : int(chunk.shape[0])]
                    chunk = np.clip(chunk, -1, 1)
                    chunk = (chunk * 32767).astype(np.int16)
                    yield chunk.tobytes()
                    print(f"[{self.branding}Debug] Yielded audio chunk {i}") if self.debug_tts else None
                print(f"[{self.branding}Debug] Streaming audio generation completed") if self.debug_tts else None
            else:
                print(f"[{self.branding}Debug] Non-streaming audio generation", output_file) if self.debug_tts else None
                torchaudio.save(output_file, torch.tensor(output["wav"]).unsqueeze(0), 24000)
                print(f"[{self.branding}Debug] Non-streaming audio generation completed") if self.debug_tts else None

        # apitts Methods
        elif self.current_model_loaded.startswith ("apitts"):
            # Streaming only allowed for XTTSv2 local
            if streaming:
                raise ValueError("Streaming is only supported in XTTSv2 local")

            # Set the correct output path (different from the if statement)
            print(f"[{self.branding}Debug] Using apitts") if self.debug_tts else None
            self.model.tts_to_file(
                text=text,
                file_path=output_file,
                speaker_wav=wavs_files,
                language=language,
                temperature=temperature,
                length_penalty=self.model.config.length_penalty,
                repetition_penalty=repetition_penalty,
                top_k=self.model.config.top_k,
                top_p=self.model.config.top_p,
                speed=speed,
            )

        # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        # ↓↓↓ Keep everything below this line ↓↓↓
        # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓ 
        generate_end_time = time.time()  # Record the end time to generate TTS
        generate_elapsed_time = generate_end_time - generate_start_time
        print(f"[{self.branding}GEN] \033[94mTTS Generate: \033[93m{generate_elapsed_time:.2f} seconds. \033[94mLowVRAM: \033[33m{self.lowvram_enabled} \033[94mDeepSpeed: \033[33m{self.deepspeed_enabled}\033[0m")
        if self.lowvram_enabled and self.device == "cuda" and self.tts_narrator_generatingtts == False:
            await self.handle_lowvram_change()
        self.tts_generating_lock = False # Unlock the TTS generation queue to allow TTS generation requests to come in again.
        print(f"[{self.branding}Debug] generate_tts function completed") if self.debug_tts else None
        return


