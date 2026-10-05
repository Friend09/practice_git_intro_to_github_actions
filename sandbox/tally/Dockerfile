FROM python:3.12-slim
WORKDIR /app
COPY tally/ tally/
CMD ["python", "-c", "from tally.add import add; print(add(2, 3))"]
