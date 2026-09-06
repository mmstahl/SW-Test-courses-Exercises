FROM jupyter/scipy-notebook:latest

COPY student-workspace/ /home/jovyan/work/

WORKDIR /home/jovyan/work

USER jovyan

CMD ["start-notebook.sh", "--NotebookApp.token=''", "--NotebookApp.password=''", "--ip=0.0.0.0", "--port=8888"]
