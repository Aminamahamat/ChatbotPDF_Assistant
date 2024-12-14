from langchain.chains import RetrievalQA
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.callbacks.manager import CallbackManager
from langchain_community.llms import Ollama
from langchain_community.embeddings.ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
import streamlit as st
import os
import time

# Creation des repertoires s'ils n'existent pas 
if not os.path.exists('files'):
    os.mkdir('files')

if not os.path.exists('jj'):
    os.mkdir('jj')


if 'template' not in st.session_state:
    st.session_state.template = """Vous êtes un chatbot bien informé qui répond en français. Vous devez donner des réponses concises et directement liées à la question posée. Limitez votre réponse à quelques phrases seulement mais bien detaillé. Si les informations ne sont pas disponibles, indiquez poliment que vous ne pouvez pas répondre.

Contexte: {context}
Historique: {history}

Utilisateur: {question}
Chatbot (en français):"""

if 'prompt' not in st.session_state:
    st.session_state.prompt = PromptTemplate(
        input_variables=["history", "context", "question"],
        template=st.session_state.template,
    )

if 'memory' not in st.session_state:
    st.session_state.memory = ConversationBufferMemory(
        memory_key="history",
        return_messages=True,
        input_key="question"
    )

if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = Chroma(
        persist_directory='jj',
        embedding_function=OllamaEmbeddings(base_url='http://localhost:11434', model="llama3.1")
    )

if 'llm' not in st.session_state:
    st.session_state.llm = Ollama(
        base_url="http://localhost:11434",
        model="llama3.1",
        verbose=True,
        temperature=0.5, 
        top_p=0.9,       
        callback_manager=CallbackManager([StreamingStdOutCallbackHandler()]),
    )


if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

st.title("PDF Chatbot")


uploaded_file = st.file_uploader("Telecharger votre PDF", type='pdf', key="file_uploader")

# chat historique
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["message"])

if uploaded_file is not None:
    
    if not os.path.isfile("files/" + uploaded_file.name + ".pdf"):
        with st.status("Analyser votre document..."):
            bytes_data = uploaded_file.read()
            with open("files/" + uploaded_file.name + ".pdf", "wb") as f:
                f.write(bytes_data)

            
            loader = PyPDFLoader("files/" + uploaded_file.name + ".pdf")
            data = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,
                chunk_overlap=200,
                length_function=len
            )
            all_splits = text_splitter.split_documents(data)

            
            st.session_state.vectorstore = Chroma.from_documents(
                documents=all_splits,
                embedding=OllamaEmbeddings(model="llama3.1")
            )
            st.session_state.vectorstore.persist()

    
    st.session_state.retriever = st.session_state.vectorstore.as_retriever()

    # Initialisation QA chain
    if 'qa_chain' not in st.session_state:
        st.session_state.qa_chain = RetrievalQA.from_chain_type(
            llm=st.session_state.llm,
            chain_type='stuff',
            retriever=st.session_state.retriever,
            verbose=True,
            chain_type_kwargs={
                "verbose": True,
                "prompt": st.session_state.prompt,
                "memory": st.session_state.memory,
            }
        )
 
    # Chat input
    if user_input := st.chat_input("You:", key="user_input"):
        user_message = {"role": "user", "message": user_input}
        st.session_state.chat_history.append(user_message)
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        with st.chat_message("assistant"):
            with st.spinner("Assistant is typing..."):
                response = st.session_state.qa_chain(user_input)
            
            message_placeholder = st.empty()
            full_response = ""
            
            # Display response as if typing
            for chunk in response['result'].split():
                full_response += chunk + " "
                time.sleep(0.05)
                message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
        
        chatbot_message = {"role": "assistant", "message": response['result']}
        st.session_state.chat_history.append(chatbot_message)

else:
    st.write("Please upload a PDF file.")
