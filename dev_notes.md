The idea:
each folder operate as a capability, each has:
    -prompt.md
    -tool.json -> store a references for thr tool need to execute this capability, the tool are requested to the main folderagent registery taht exeute them and give back the result
    -manifest.yaml -> the identity card of the capability (name, version, what task it accept and a more or less detailed description)
    -example/
        |_ some example.md

any other bonus file will be mentionned in the prompt or the yaml
the tools are in the tool registery and to be executed we must ask the executor (just like asking the office for tools)
We have now long term, short term, rag memory and a context window manager

the architecture is broken between skill/capability taht follow the sturcture detail up there the agent in itself work with memory and tool registry to build and execute the required prompt.
each capability should be self contain and we should be able to give it to any other agent or system to use it as a skill/capability

Now there is a split evolution for our agent like a pokémon, it can either become the super fast ParallelFolderAgent that can run multiple task inparralllel (it is in tit name) using the thread logic or the adaptative LearningFolderAgent whih has a module that allow it to learn at the end of each query learning from it mistake, sucess but also verifying  itoutput and checking if it match the initial request.

in a news addition each capability should now have it own manaifest.yaml to serve as identity card, each should show tha name, version, what task it accept and a more or less detailed description

We can now agrreagte the output of the capacities (yaaaay)

We want to keep the system highly modluable so i will attempet to not have any code in the capacities, leaving an agent taht can cosplay as subagent  to accompshis task

To avoid the llm rewriying it own code because now it can i guess we will implment two security policies around tool and directory access. We also have to stop the llm from lying and hallucinating.

well i was think about breaking context in a folder called context and in there will be files that give context on the current conversation taht the llm can then use mocing fowrad those file will be modifialble and work like claude.md file

i should write a linkedn in post now but i don't have something to show with the post like i don't have the repo or an ui to let the poeple see and i don't think they like code that much, also the context folder is supposed to avoid context rot and halluciantion and allow so form of communication between capabilities  

To avoid burning token and money and computing power and RAm and all lot of other things i will introduce a router that decide if a task is complexe enough to involve the planner, so basicallly if a task is really complex i invlove the planner to break it in shorter task but f it can be done by one cpacity we send it directly there saving time and not invloving the planner all the time . it would be baked in the agent so it will be easier and a lot less context to maintain

Now i also have to implment a dual model architecture for better task orientation to save up token and context window because passing 15 manifest is appraently a war crime so here we are, will be a nice upgrade addition, it is not a new from more of a possible new from of the agent

The agent can now fill a file with the output of each tasks progressively and now task can ask for the output they need from the stactchpad to do thier job

now i will add max retrie for the tool, timeout and catching thier output for debugging, the code will be written, saved an exceuted in a tmp file to make sure it is safe

we adding semantic meaning search now because apprently the memory serach by word similarity not meaning similarity

first day of the data_analyst capability (yaaaay)

so basically i have added a dualagent evolution,simply because a router and a planner where doing to much msitake and taking up too much context so i basiaclly use a smaller model to route ersuets and anser small one but a bigger one for complex stuff

What if the agent could upgarde itself? like it sees a flaw in it prompt, memory, tools, capabilities or whatever and fix it self? Or event switicng in parralel, dual and  learning modz depending of the user  or the task at hand

i should also make it pas the gaia benchmark, just to see if we can beat it

okay it's decided i will allow it to explore a dockrize pc, i will use  a docker container with a debian instance and see how it do.

before that i should give it img capabilities wather it is with generation or analysis.on second though just vision will be enough.

update: Docker sandbox setup completed with Debian slim base, non-root agent user (UID 1000), read-only rootfs, tmpfs for /tmp and /home/agent, dedicated workspace, resource limits (cpu, ram, pids), dropped capabilities (--cap-drop=ALL), seccomp profile, full lifecycle management (create, start, stop, destroy, reset), and CLI manager tool.
