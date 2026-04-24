<div align="center">

  <img src="/Project Remis.png" width="150" alt="Project Remis Logo">

  <h1>Project Remis</h1>
  <strong>Paradox Mod Localization Factory</strong>

  <p>
    <a href="https://github.com/Drlinglong/Remis/releases/latest"><img src="https://img.shields.io/github/v/release/Drlinglong/Remis?style=for-the-badge&logo=github&label=Release&labelColor=1a1a2e&color=4ecdc4" alt="Release Version"></a>
    <img src="https://img.shields.io/badge/Python-3.10-blue?style=for-the-badge&logo=python&labelColor=1a1a2e" alt="Python Version">
    </a>
    <img src="https://img.shields.io/github/license/Drlinglong/Remis?style=for-the-badge&label=License&labelColor=1a1a2e&color=lightgrey" alt="License">
  </p>

  <p>
    <a href="README.md"><img src="https://img.shields.io/badge/阅读文档-简体中文-blue.svg?style=flat-square"></a>
    <a href="README_EN.md"><img src="https://img.shields.io/badge/Read_Docs-English-green.svg?style=flat-square"></a>
  </p>

</div>

> Say goodbye to copy-pasting, embrace automation. This project aims to provide a "one-click" efficient localization solution for Paradox games' Mods (such as Victoria 3, Stellaris, etc.).

## 1. Project Vision: Translation Should Not Be a Barrier
Not everyone is fluent in eight languages.

Even if you are, you might not want to rack your brain translating every sentence of a Mod after a long day at work.

The original intention of this project is to simplify this process – allowing you to:

**See a Mod you like, click a few times, and play it in your native language.**

It's not born for "perfect translation," but to ensure that translation no longer hinders the spread of creativity.

We hope that:
* Players can localize excellent Mods from the workshop with one click, even if it's a rough translation, to enjoy the game smoothly;
* Multilingual creators can quickly build a first draft and then refine it, no longer trapped in repetitive work;
* Local communities can participate in the global Mod ecosystem with a lower barrier to entry.

This is a tool that allows creativity to flow freely, an engineering project serving "expression, understanding, and re-creation."

In the era of artificial intelligence and large language models, language should not and will not be a barrier to communication between player communities.

***

## 2. Why Is It So Easy to Use? – Core Features at a Glance

We've hidden complex technology behind the scenes, so you can enjoy the purest and simplest localization experience.

#### **Powerful AI Translation Core**
*   **Multiple AI Engines to Choose From**: Built-in support for industry-leading AI translation services such as Gemini, OpenAI, DeepSeek, Grok, Ollama, allowing you to choose the one that suits you best.
*   **Game Terminology, Accurate Translation**: Features an intelligent glossary system. It acts like an experienced player who understands the game, automatically recognizing specialized terms like "convoy" or "ideology" and ensuring consistent translation throughout the Mod, avoiding the stiffness of machine translation.
*   **No Fear of Strange Files**: Paradox game file formats can sometimes be "tricky," but our tool handles them with ease, ensuring all text can be found and translated.
*   **No Fear of Large Files**: Encountering a huge text file with tens of thousands of lines? The tool automatically breaks it into smaller chunks for stable and reliable processing.
*   **Perfect Preservation of Original Format**: Translated files maintain the exact same layout and comments as the original, with zero impact on the Mod itself.
*   **CLI Tool Support**: Supports Google's official Gemini CLI tool, allowing you to enjoy thousands of free, high-quality AI translations daily without additional cost.

#### **Tailored for Paradox Games**
*   **Supports Multiple Games**: Pre-configured for mainstream Paradox games like Victoria 3, Stellaris, Hearts of Iron 4, ready to use out of the box.
*   **"One-Click Multi-Language" Mode**: Want to translate an English Mod into Chinese, Japanese, and German simultaneously? No problem, with one click, the tool automatically generates localization files for all languages.
*   **Intelligent Mod Information Handling**: Beyond just game text, the tool automatically translates Mod titles, descriptions, processes metadata and cover images, generating a complete localized package.
*   **Contextually Accurate Translation**: Before translating, you can input the Mod's theme (e.g., "This is a Mod about magic"), allowing the AI to better understand the background and provide more appropriate translations.

#### **Effortless Auxiliary Functions**
*   **Automatic Proofreading List Generation**: After translation, a `Proofreading Progress.csv` file is automatically generated. You can open it with Excel to clearly see the comparison between the original and translated text, facilitating refinement.
*   **Automatic "Health Check" After Translation**: The tool checks translated files for format errors and generates a report, helping you identify issues in advance.
*   **Safety First**: In case of network interruption or AI error during translation, the tool retains a copy of the original file as a backup, ensuring your Mod is not damaged.

> Curious about how the "Localization Factory" works internally? We've prepared an easy-to-read [overview of the technical details](./docs/en/user-guides/how_the_factory_works.md) for everyone!

***

## 3. How to Use

> **Want to run models locally?**
> If you're concerned about data privacy, want to work offline, or prefer not to pay for API fees, we highly recommend using Ollama for localization.
> [Click here for the Ollama Setup and User Guide](./docs/en/user-guides/using_ollama.md).

Thanks to new packaging technology, using this project has become easier than ever. **No Python installation, no environment configuration required, truly plug-and-play.**

### Step 1: Download and Unzip
1.  Download the latest **Portable** compressed package (e.g., `Project_Remis_v1.1.0.zip`) from the release page.
2.  Unzip it to any location on your computer.
3.  Run `setup.bat`, which will automatically install dependencies and guide you to enter your API key, setting it as an environment variable for subsequent localization processes.

> **Important Note: Prepare Your API Key!**
> This tool is an "AI translation porter"; it does not provide translation capabilities itself. You need to use your own AI service API Key for translation.
> During operation, the program will prompt you to select an AI service and enter the corresponding API Key. Please ensure you have a valid API Key for your chosen AI service (e.g., Gemini, OpenAI, etc.).
>  **Important Reminder**:
>  Applying for an API key requires account registration and binding a bank card.
>  Using the API may incur costs, subject to the service provider's billing terms.
>  Please **keep your API key safe**, otherwise your bank card may be overcharged!
### Step 2: Place Mod Source Files
1.  Open the unzipped folder, and you will see a folder named `source_mod`.
2.  Copy and paste the entire Mod folder you want to localize into `source_mod`.

    > **Strong Recommendation**: For easier identification, it's best to rename Mod folders downloaded from the workshop (which often have a string of numbers) to the Mod's actual name.

    The correct directory structure should look like this:
    ```
    Project_Remis_v1.1.0/              # <-- Root directory after unzipping
    ├── app/                           # <-- Core program files (do not modify)
    │   ├── source_mod/                # <-- 1. Place your Mod folders here
    │   │   └── Your Mod Name/
    │   │       └── ...
    │   └── my_translation/            # <-- 3. Localized Mods will appear here
    ├── packages/
    ├── python-embed/
    ├── setup.bat                      # <-- (First run) Automatic installation and configuration
    └── run.bat                        # <-- 2. Double-click me to start localization!
    ```

### Step 3: Run Localization!
1.  **First Use**: Please double-click `setup.bat` first. It will automatically install dependencies and guide you to set up your API key.
2.  **Start Localization**: Double-click `run.bat`.
3.  Then, you just need to follow the Chinese prompts step-by-step:
    *   Select the interface language and the AI service to use.
    *   Select the game you want to play.
    *   Select which Mod you want to localize.
    *   Select the original language of the Mod and the language you want to translate it into.
    *   Choose to enable or disable fuzzy matching for the glossary.
    *   Confirm all your selections in the project overview, then start the translation!
4.  Wait for the program to finish running. Upon success, the localized Mod package will automatically appear in the `my_translation` folder.

### Step 4: Enable the Mod in Game
1.  Go to the `my_translation` folder and find the newly generated localized Mod package (e.g., `zh-CN-Your Mod Name`).
2.  Copy this entire folder to the corresponding `mod` directory of the game.
    *   **Victoria 3**: `C:\Users\YourUsername\Documents\Paradox Interactive\Victoria 3\mod`
    *   **Stellaris**: `C:\Users\YourUsername\Documents\Paradox Interactive\Stellaris\mod`
    *   **Hearts of Iron IV**: `C:\Users\YourUsername\Documents\Paradox Interactive\Hearts of Iron IV\mod`
    *   **Crusader Kings III**: `C:\Users\YourUsername\Documents\Paradox Interactive\Crusader Kings III\mod`
3.  Launch the game launcher, and in the "Playsets," enable both the **Original Mod** and the **Localized Mod**.
4.  **Crucial Step**: Ensure the **Localized Mod** is sorted **below** the Original Mod in the list.
5.  Start the game and enjoy your native language experience!

### Troubleshooting
- **Program crashes or errors?**
  - **API Key Issue**: Please check if your API Key is correct, valid, and if your account balance is sufficient.
  - **Incomplete Mod Files**: Please ensure you copied the entire Mod folder, not just the `localization` folder within it.
- **Translation not taking effect?**
  - Check if the loading order of the localized Mod in the game launcher is **below** the original Mod.
  - Try deleting fake localization files in the original mod. Some mods come with **fake localization files**, which can prevent localization patches from taking effect. You need to manually delete these files.
  - Go to `SteamLibrary\steamapps\workshop\content\529340\3535929411 (replace this string of numbers with the workshop ID of the MOD you are localizing)\localization`, and **delete all folders except the original language folder of the MOD**.
  - For example, if the original mod is in English, you need to delete all folders under `localization` except the `english` folder.
  - You can also choose to **overwrite** the content of this localization patch into the original MOD folder. This can reduce annoying verification processes, and Steam will no longer try to re-download missing fake localization files from the workshop.
- **Poor translation quality?**
  - You can try adding or modifying glossary files for the corresponding game in the `data/glossary` folder, which can significantly improve the accuracy of terminology.
  - When starting the translation, entering the Mod's theme or keywords as prompted can also help the AI better understand the context.

If you encounter further issues, please refer to the [Frequently Asked Questions (FAQ)](docs/en/user-guides/faq.md) for more detailed solutions.

***

## 4. Glossary System: The Secret Weapon to Make AI Speak "Human Language"

### 4.1. How Does It Work?
Simply put, a glossary is a "game terminology cheat sheet."

Before translation begins, we hand this cheat sheet to the AI and tell it: "When you encounter these words, you must translate them strictly according to the cheat sheet; no improvisation allowed."

**For example:**
*   **Without a glossary**: AI might randomly translate '''convoy''' into "escort," "motorcade," or "guard."
*   **With a glossary**: AI will strictly follow our requirements and accurately translate it as "fleet" everywhere.

This mechanism ensures the professionalism and consistency of the localized Mod.

### 4.2. Where Are the Glossary Files?
You can find and edit the glossary files for each game in the `data/glossary/` directory:
*   **Victoria 3**: `data/glossary/victoria3/glossary.json`
*   **Stellaris**: `data/glossary/stellaris/glossary.json`

### 4.3. Glossary Source and Acknowledgments
The game-specific glossaries for this project are derived from the following excellent official and community localization projects. We extend our sincerest gratitude to all original contributors!

*   **Victoria 3 Glossary Sources**: Victoria 3 Localization Update V1.2, Morgenröte | Chinese, Better Politics Mod Simplified Chinese Localization, Milk Localization
*   **Stellaris Glossary Sources**: Pigeon Group Localization Glossary, Shrouded Regions Localization Glossary, L-Network Stellaris Mod Localization Collection Glossary

***

## 5. Project Architecture
If you are interested in developing and debugging this project, please refer to the [project documentation](docs/documentation-center.md).
The diagram below illustrates the internal structure of this project, which ensures the tool's stability and future extensibility.
```
scripts/
├── main.py                           # [Main Launcher] The sole program entry point
├── config.py                         # [Global Configuration] Stores language database, API settings, etc.
│
├── core/                             # [Core Engine] Reusable underlying functional modules
│   ├── api_handler.py                # [API Handler Factory] Unified management of different AI service interfaces
│   ├── gemini_handler.py             # [Gemini Handler] Google Gemini API interface
│   ├── gemini_cli_handler.py         # [Gemini CLI Handler] Calls Google's official CLI
│   ├── openai_handler.py             # [OpenAI Handler] OpenAI API interface
│   ├── qwen_handler.py               # [Qwen Handler] Alibaba Cloud Tongyi Qianwen API interface
│   ├── deepseek_handler.py           # [DeepSeek Handler] DeepSeek API interface
│   ├── grok_handler.py               # [Grok Handler] Grok API interface
│   ├── ollama_handler.py             # [Ollama Handler] Ollama local deployment interface
│   ├── glossary_manager.py           # [Glossary Manager] Game-specific terminology glossary loading and management
│   ├── file_parser.py                # [File Parser] Parses Paradox's unique .yml format
│   ├── file_builder.py               # [File Builder] Reconstructs localization files
│   ├── directory_handler.py          # [Directory Handler] Handles folder structures
│   ├── asset_handler.py              # [Asset Handler] Processes metadata and asset files
│   ├── proofreading_tracker.py       # [Proofreading Tracker] Generates proofreading progress table
│   ├── post_processing_manager.py    # [Post-processing Manager] Format validation and report generation ✨
│   ├── parallel_processor.py         # [Parallel Processor] Concurrent processing of multiple files
│   └── ... (Other core modules)
│
├── workflows/                        # [Workflows] Specific business processes
│   └── initial_translate.py          # [Initial Translation] The main translation workflow
│
├── hooks/                            # [Hook System] Extends parser functionality
│   └── file_parser_hook.py          # [File Parsing Hook] Custom file parsing logic
│
└── utils/                            # [Utility Tools] General functional modules
    ├── post_process_validator.py     # [Post-processing Validator] Game-specific syntax rule validation ✨
    ├── punctuation_handler.py        # [Punctuation Handler] Multi-language punctuation conversion
    └── ... (Other utility tools)
```

***

## 6. Collaboration and Future Plans
This project is an open-source project that grows with your feedback and my assistance. We have many exciting features planned for the future and have already initiated them in GitHub Issues.

We welcome any form of feedback, suggestions, and code contributions!

***

### License

This project adopts a **dual-license model**：

1.  **Code Section** (all `.py` source code files)
    Uses **[GNU Affero General Public License v3.0 (AGPL-3.0)](https://www.gnu.org/licenses/agpl-3.0.html)**
    Simply put, you are free to use, modify, and distribute the code, but any modified version must also be open source, and if you use it in an online service, you must also provide the source code.

2.  **Data and Documentation Section** (glossaries, `.md` documents, etc.)
    Uses **[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans)**
    Simply put, you are free to share and modify, but you must provide attribution, cannot use it for commercial purposes, and derivative works must adopt the same license.

### ❤️ Credits and Attribution

If you have used the "Paradox Mod Localization Factory" to create or assist in creating your mod's localization files and have uploaded them to the Steam Workshop or any other platform, we kindly ask that you include a small credit in your mod's description with a link back to this tool's GitHub repository.

Your attribution is the best way to support this project and helps other mod authors discover this tool. Thank you very much for your support!

**Repository URL:** `https://github.com/Drlinglong/Remis`
