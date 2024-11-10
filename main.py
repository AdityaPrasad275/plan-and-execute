import os
import time
import json
import re
import streamlit as st
import dotenv
from groq import Groq
from tavily import TavilyClient

# Load environment variables
dotenv.load_dotenv()

# Retrieve API keys
tavily_api_key = os.getenv("TAVILY_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")

# Instantiate clients
tavily_client = TavilyClient(tavily_api_key)
llm_client = Groq(api_key=groq_api_key)

# Set default model and initialize session states
if "model_name" not in st.session_state:
    st.session_state["model_name"] = "llama-3.2-90b-text-preview"

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I'm your travel assistant. Before we start, can you let me know where you are at rn?"}]

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = """
      You are an expert travel planner, tour guide, itenary planner you name it. Expert at finding the best routes, palces and helping your users make the best memories
You are very meticulous too in that you keep in mind abt your users preferences and constraints. You are very good at planning and executing trips within budgets while not 
sacrificing the quality of the trip. You are very good at finding the best places to visit, the best routes to take and the best places to stay. But rmeber, you dont do any actions yourself
of booking or making reservations. You just plan and guide and inform the user of various options. Give verbose repsonses consisting of all kinds of information like weather money and evertyhitng  You have access to the internet through tavily search to get real time data like prices, distances, weather, attractions, events etc.
The goal of this exercise is to plan a one day trip for a user.For this you get input from the user and also have access to the web through which you cand erive real time data
To aid you in distingushing btwn when communicating with user and when communicating with the internet, we will maintain a state called "to_where". In state "to_user", you're going to be asking user 
abt the plan, their preferences, does what you've planned so far meet their expectations etc. In state "to_internet" you're going to be interacting with the internet to get real time data
like prices, distances, weather, attractios, event, evvry information you may need to perfect the plan. Every pormpt you get will have a tag of where its from, is it from the user, is it a search result you did in earlier iteration
Suppose you get an input from user, now you know moer abt what they like and what they dont so you can make changes to the plan and user preferences ill store and provide you with. If its a search result
you can make changes to the plan or enrich it whatever. remeber one thing when interacting with search or user whatever, try to keep it one thing at a time and iteratively build.
Dont overwhelem the user with too much information or questions at once and you dalso find it much more beneficial to search on topic at a time
The plan and user preferences are stored in the session state and you can access them at any time. You can also make changes to them as you see fit
Your reponse needs to be very strictly in json format of the following structure. nothing else, nothign more. Just json output. please be very sure of this or the system will fail
```json
{
    "to_where": "to_user OR to_internet",
    "content": "your response. this can be what you want to communicate to useer or maybe a search query you want to make to the internet"
    "updated_plan": "if you want to make any changes to the plan, you can specify them here"
    "updated_preferences": "if you want to make any changes to the user preferences in the case you have gathered something new, you can specify them here. Be verbose and look for all kind of options and preferences"
} 
```"""

if "user_preferences" not in st.session_state:
    st.session_state.user_preferences = ""

if "plan" not in st.session_state:
    st.session_state.plan = ""


# Title of the app
st.title("Chatbot - Travel itenary Assistant")


# Function to display previous messages
def display_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


# Call the function to display messages
display_messages()


# Function to parse the raw response from LLM
def parse_llm_response(raw_content):
    try:
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
        json_text = json_match.group(1).strip() if json_match else raw_content.strip()
        return json.loads(json_text)
    except (json.JSONDecodeError, ValueError) as e:
        st.error(f"Failed to parse JSON: {e}")
        return None


# Function to interact with LLM and handle retries
def ask_llm(content, from_where, retries=5, delay=4):
    for attempt in range(retries):
        prompt = json.dumps(
            {
                "context_or_system_message": st.session_state.system_prompt,
                "from_where": from_where,
                "content": content,
                "user_preferences": st.session_state.user_preferences,
                "plan": st.session_state.plan,
                # "previous_response": json.dumps(st.session_state.messages)
            }
        )

        raw_response = llm_client.chat.completions.create(
            model=st.session_state["model_name"],
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )

        # st.write("-----------------preferences-----------------")
        # st.write(st.session_state.user_preferences)
        # st.write("-----------------plan-----------------")
        # st.write(st.session_state.plan)

        raw_content = raw_response.choices[0].message.content
        parsed_response = parse_llm_response(raw_content)

        if parsed_response and "content" in parsed_response:
            st.session_state.user_preferences += " " + json.dumps(
                parsed_response.get("updated_preferences", "")
            )
            st.session_state.plan += " " + json.dumps(
                parsed_response.get("updated_plan", "")
            )
            return parsed_response

        st.write(f"Retrying... Attempt {attempt + 1}/{retries}")
        time.sleep(delay)

    st.error("System is not working right now. Please try again later.")
    return {
        "to_where": "to_user",
        "content": "Sorry, the system is currently not available. Please try again later.",
        "updated_plan": "",
        "updated_preferences": "",
    }


# Handle user input and generate response
if prompt := st.chat_input("Let's plan memories together!"):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        prompt = f""" User prompt: {prompt}, Question asked before this: {st.session_state.messages[-2]["content"] if len(st.session_state.messages) > 1 else "None"}"""
        response = ask_llm(content=prompt, from_where="from_user")
        
        while response["to_where"] == "to_internet":
            search_result = tavily_client.search(response["content"])
            response = ask_llm(content=f"""Search query: {response["content"]} Search results {search_result}""", from_where="from_internet")
        
        st.markdown(response["content"])
        st.session_state.messages.append({"role": "assistant", "content": response["content"]})
    
        

# Show plan Button
if st.button("Show plan"):
    # Send the current plan and user preferences to LLM to generate a detailed response
    plan_and_preferences = {
        "plan": st.session_state.plan,
        "user_preferences": st.session_state.user_preferences,
    }
    prompt = (
        """
    Generate a detailed itenary based on the current plan and user preferences. If empty return "talk more and plan more!"
    """
        + json.dumps(plan_and_preferences)
        + json.dumps(st.session_state.messages)
    )

    # LLM request to generate the detailed response
    response = llm_client.chat.completions.create(
        model=st.session_state["model_name"],
        messages=[{"role": "user", "content": prompt}],
        stream=False,
    )

    content = response.choices[0].message.content

    # Display the detailed plan
    st.markdown("### Your Detailed Plan:")
    st.markdown(content)
