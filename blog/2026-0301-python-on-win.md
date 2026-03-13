# Developing with Python on Windows using VSCode, Git Bash, FAR, ConEmu, and Conda (No WSL Required)

In the age of WSL2 and Docker, the art of the "Native Windows" development environment is somewhat lost. While Linux subsystem is fantastic, it introduces a layer of abstraction (and file system latency) that isn't always necessary. Sometimes, you just want raw speed, direct access to Windows APIs, and a workflow that feels snappy.

Granted that running some things on Windows can be tricky, I never encountered a compatibility problem that I was not able to solve, from GUI python apps, to heavy numpy code and pytorch models running on GPU. Having a large stack of apps for hardware that only exist on Windows, it is not much of a choice - as I can't make myself carry 2 laptops around. That settles Windows choice for me.

As for the IDE...

I like using VS Code with all its nice extensions and integrations. However, I often find myself using FAR Manager where I don't have to touch the mouse to get things done quickly.

If you are a fan of Orthodox File Managers and keyboard-centric workflows, this guide is for you. We are going to build a rock-solid Python environment using **Git Bash**, **MSYS2**, **ConEmu**, **FAR Manager**, and **Conda**, tied together with a few clever hacks.

## The Stack

1. **Git for Windows (MSYS2):** For the Unix tools (`git`, `bash`, `ls`, `grep`, `sed`) without the Linux kernel.
2. **Miniconda:** For Python environment management.
3. **FAR Manager:** The grandson of a legendary blue-screen file manager.
4. **ConEmu:** The best terminal emulator for Windows.

## Download Links

* **Git for Windows:** [gitforwindows.org](https://gitforwindows.org/)
* **MSYS2:** [MSYS2](https://www.msys2.org/)
* **Miniconda:** [docs.anaconda.com/miniconda/](https://docs.anaconda.com/miniconda/)
* **FAR Manager:** [farmanager.com/download.php](https://www.farmanager.com/download.php)
* **ConEmu:** [conemu.github.io](https://conemu.github.io/)
* **FarCall plugin:** [FarCall on Plugring](https://plugring.farmanager.com/plugin.php?pid=823&l=en)
* **GitBranch plugin:** [GitBranch on Plugring](https://plugring.farmanager.com/plugin.php?pid=978&l=en)
* **GitShell plugin:** [GitShell on Plugring](https://plugring.farmanager.com/plugin.php?pid=972&l=en)
* **GitAutocomplete plugin:** [GitAutocomplete on Plugring](https://plugring.farmanager.com/plugin.php?pid=967&l=en)

## Step 1: The Foundation (Git & MSYS2)

First, install **Git for Windows**. During installation, ensure you select the option to add Unix tools to your PATH. This gives you the lightweight MSYS2 backend, allowing you to run standard bash commands directly in Windows `cmd.exe`. It is also possible to install full **MSYS2** separately for more tools than what Git for Windows has.

## Step 2: Python Management (Miniconda)

Download and install **Miniconda**.

* **Crucial Step:** Do *not* add Conda to your system PATH during installation. It messes up other tools. We will inject it surgically later.

## Step 3: The Commander (FAR Manager)

Install **FAR Manager** (x64). If you haven't used it, it’s a modal, two-panel file manager that relies entirely on keyboard shortcuts. It is the successor to the legendary Norton Commander and is the fastest way to navigate a file system, period. It also supports mouse really well, but you will rarely need it.

Add 2 plugins (download from PlugRing) - `FarCall` and `GitBranch`. FarCall will enable seamless conda operation under FAR Manager. GitBranch is handy to show current branch in the command prompt using `%GITBRANCH%` variable.

Make sure to download the same x64 architecture as the FAR Manager. Copy plugins (directory with `.dll`) into FAR Manager plugins directory at `C:\Program Files\Far Manager\Plugins\`.

## Step 4: The Console (ConEmu)

Install **ConEmu**. This will be the container for our FAR Manager.

1. Open ConEmu Settings (`Win + Alt + P`).
2. Go to **Startup > Tasks**.
3. Create a new task named `{Far}`.
4. We will come back to the command for this task in a moment. Just save it for now.

## The Hacks: Tying it all together

Here is where the magic happens. We want FAR to open inside ConEmu, with Conda pre-activated, and a prompt that shows our Git branch and active Python environment.

### Hack 1: Solve "Conda in FAR" Problem

Since we didn't add Conda to the global PATH, standard `cmd` windows won't know what `conda` or `python` is. We need a hook to run batch script when `cmd.exe` starts. We can use `conda init cmd.exe` command - it will add registry key `Autorun` under `HKCU/Software/Microsoft/Command Processor/` that initializes the Conda environment (`if exist "C:\ProgramData\miniconda3\condabin\conda_hook.bat" "C:\ProgramData\miniconda3\condabin\conda_hook.bat"`).

This is sufficient for plain `cmd.exe`. However, FAR Manager works on top of `cmd.exe` and launches commands in subprocesses, so the changes of environment variables are not propagated back to FAR process, so `conda activate` won't work out of the box.

We will add a macro file to FAR Manager to fix that. Create file `C:\Users\%USERNAME%\AppData\Roaming\Far Manager\Profile\Macros\scripts\CondaInit.lua` and paste the following content:

```lua
Macro {
  description = "FAR startup Conda hook";
  area = "Shell";
  flags = "RunAfterFARStart";
  action=function()
    Keys("Esc")
    print("call:C:\\ProgramData\\miniconda\\condabin\\conda_hook_far.bat")
    Keys("Enter")
  end;
}
```

This macro runs upon FAR Manager startup, and loads conda hook using special FarCall `call:`. FarCall copies environment variables back to FAR Manager after the command exits, enabling conda fully.

Or almost. Original file `conda_hook.bat` creates an alias for `conda` commands, but the alias is not using FarCall, so it also won't work under FAR Manager.

We will need to edit the hook file, or rather create a new one. Create file `C:\ProgramData\miniconda\condabin\conda_hook_far.bat` (you will need to use admin privileges) and paste this content into it:

*Note: Adjust the Miniconda path if you installed it elsewhere.*

```batch
:: MODIFIED FROM CONDA ORIG: Use FAR Manager FarCall plugin

:: Copyright (C) 2012 Anaconda, Inc
:: SPDX-License-Identifier: BSD-3-Clause
:: The file name is conda_hook.bat rather than conda-hook.bat because conda will see
:: the latter as a 'conda hook' command.

@IF DEFINED CONDA_SHLVL GOTO :EOF

@FOR %%F IN ("%~dp0") DO @SET "__condabin_dir=%%~dpF"
@SET "__condabin_dir=%__condabin_dir:~0,-1%"
@SET "PATH=%__condabin_dir%;%PATH%"
@SET "CONDA_BAT=%__condabin_dir%\conda.bat"
@SET "CONDA_BATA=%__condabin_dir%\activate.bat"
@SET "CONDA_BATD=%__condabin_dir%\deactivate.bat"
@FOR %%F IN ("%__condabin_dir%") DO @SET "__conda_root=%%~dpF"
@SET "CONDA_EXE=%__conda_root%Scripts\conda.exe"
@SET __condabin_dir=
@SET __conda_root=

@if defined FARHOME (
  @DOSKEY conda=call:"%CONDA_BAT%" $*
  @DOSKEY activate=call:"%CONDA_BATA%" $*
  @DOSKEY deactivate=call:"%CONDA_BATD%" $*
) else (
  @DOSKEY conda="%CONDA_BAT%" $*
  @DOSKEY activate="%CONDA_BATA%" $*
  @DOSKEY deactivate="%CONDA_BATD%" $*
)

@SET CONDA_SHLVL=0
```

It uses `call:` notation when it runs under FAR Manager. It also adds aliases for `activate` and `deactivate` commands (missing in the original version of the hook).

Now, go back to **ConEmu Settings > Startup > Tasks > {Far}**. Set the command to:

```dos
set "FARHOME=" & "C:\Program Files\Far Manager\Far.exe" /w /p"%ConEmuDir%\Plugins\ConEmu;%FARHOME%\Plugins;%FARPROFILE%\Plugins" prompt $P (a)%GITBRANCH%() $G
```

This command includes modified prompt that uses Conda version (`%PROMPT%`) and Git branch (`%GITBRANCH%`) with some color.

Now, when you open ConEmu, you are in FAR Manager, and if you type `conda list` or `conda activate XXX` in the command line, it works instantly and selects python environment. The prompt shows which environment is selected, as well as current Git branch.

### Hack 2: Visual Integration (ConEmu + FAR)

To make FAR look modern and handle mouse input correctly within ConEmu:

1. In ConEmu Settings, go to **Integration > ANSI execution**.
2. Check **"ANSI and xterm sequences"**.

For integrations to work, either use argument `/p"%ConEmuDir%\Plugins\ConEmu;...` in FAR Manager command when configuring it in ConEmu Settings > Tasks > {Far}, or alternatively install ConEmu plugin into FAR Manager (Important: do not do both!):

In FAR, install the **ConEmu plugin** (can be found in the `C:\Program Files\ConEmu\Plugins\` folder) - copy it to `C:\Program Files\Far Manager\Plugins\` folder. This allows ConEmu to handle the drawing of FAR's panels, enabling smooth resizing and true color support.

### Hack 3: Git Branch in the Prompt

FAR Manager uses the standard Windows prompt (`$P$G`) by default. When working in repos, you need to see your branch. And also displaying active conda python environment is super useful.

There's a simple `gitbranch` plugin that tracks which Git branch is active in `%GITBRANCH%` variable. Change FAR Manager prompt: open menu > Options > Command prompt, and edit it to:

```dos
(a)%GITBRANCH%() %PROMPT%
```

We can also add `prompt (a)%GITBRANCH%() %PROMPT%` to {Far} command in ConEmu settings.

With that you get a beautiful prompt with Python versions and Git branches right inside the FAR command line.

*Pro-tip:* For true integration, install **Clink**. It injects Readline capabilities (bash-like editing) into `cmd.exe`. FAR works beautifully with Clink.

### Hack 4: VS Code

If you use VS Code alongside FAR, you want to open files from the FAR command line easily.

Inside FAR, you just point the cursor at a file and type `code` Space, then hit `<Ctrl-Enter>` (to paste the filename) and hit Enter to launch VS Code - it will open the file.

One thing that was not working - `conda init --all` is supposed to add hooks to all bash variants, but it was missing the one in MSYS2 `C:\msys64\home\$USER$\.bash_profile`. Make sure to copy conda hooks to .bash_profile in all locations.

```bash
...
# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
if [ -f '/c/ProgramData/miniconda3/Scripts/conda.exe' ]; then
    eval "$('/c/ProgramData/miniconda3/Scripts/conda.exe' 'shell.bash' 'hook')"
fi
# <<< conda initialize <<<
```

The remaining small issue is that conda.exe hooks `conda ...` command, but shorthand `activate ...` and `deactivate ...` commands are not configured and won't work. Just use full `conda activate ...` and `conda deactivate ...` instead.

## The Workflow

1. **Launch ConEmu.** It boots FAR instantly.
2. **Navigate** using arrow keys.
3. **Project Management:** Navigate to your project folder.
4. **Environment:** Type `conda activate my-project` right in the FAR command line. The prompt updates.
5. **Edit:** Press `F4` to edit config files in FAR's internal editor, or `code .` to open the full IDE.
6. **Run:** `python main.py`.
7. **Git:** Use the FarGit plugin (`F11` > Git) to commit/push without leaving the keyboard.

## Bonus

Install `GitShell` and `GitAutocomplete` plugins into FAR Manager to boost working with Git repos in commander mode.

## Conclusion

You don't always need a Linux kernel to do serious Python development. By leveraging the speed of keyboard navigations with FAR Manager and the flexibility of Conda, wrapped in the modern interface of ConEmu, you get a development environment that is fast, portable, and 100% native.
