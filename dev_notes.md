first idea:
each folder operate as a capability, each has:
    -prompt.md
    -tool.json -> store a references for thr tool need to execute this capability, the tool are requested to the main folderagent registery taht exeute them and give back the result
    -manifest.yaml -> the identity card of the capability (name, version, what task it accept and a more or less detailed description)
    -example/
        |_ some example.md

any other bonus file will be mentionned in the prompt or the yaml

the architecture is broken between skill/capability taht follow the sturcture detail up there the agent in itself work with memory and tool registry to build and execute the required prompt.
each capability should be self contain and we should be able to give it to any other agent or system to use it as a skill/capability

in a news addition each capability should now have it own manaifest.yaml to serve as identity card, each should show tha name, version, what task it accept and a more or less detailed description

We want to keep the system highly modluable
