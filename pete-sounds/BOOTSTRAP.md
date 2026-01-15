I'd like to start a new project call "pete-sounds".

It needs:
    - to initialize a git repository for the project

    - Create a script to install the FastVLM from huggingface that can achieve the lowest possible TBT latency on my m4 pro macbook with 48gb of RAM
        - Include this in the initial commit

    - Create a program (I'm agnostic to language) for running the video model with my logitech brio webcam as the input device.
        - The program should:
            - run the installed FastVLM model inference
            - source my webcam feed at as low a fidelity (downsampled) as is possible to achieve sub-20ms TBT latency
            - source a prompt file `DIRECTOR.md`
            - output text tokens from the model to stdout while the program is running
            - exit program with ctrl-c (and inform the user of this at startup)
            - provide a very simple help flag
        - Include this in the initial commit

    - Create a `DIRECTOR.md` promptfile to configure the video inference. Optimize and format this for the given FastVLM model:
        ```
        Role: The director conducts an infinitely running soundtrack of a livestream. Describe the colors, moods, objects, and entities, and general vibes to your output.
        Role: The composer takes cues and messages from the conductor at control rate or slower. These will be mapped into triggers and parameter changes in the soundscape engine. The composer chooses how cues and messages are interpreted and when they are scheduled within the soundtrack.

        You: are the director, and video stream is your film. Your job is to send your intention and descriptions of your work to the composer.

        Requirements:
            Because this is for music, we would like to get as close to control rate as possible. 
            The output tokens should be structured as short messages to be sent to the composer.
            Messages should look like "color: blue", "person: friend", "pet: dog", "mood: happy", etc.
            Messages should be delimited with newlines to stdout.
            Describing how it feels and what is objectively happening are both useful.
        ```
        - Include this in the initial commit

    - Remember to include this planning file in the initial commit