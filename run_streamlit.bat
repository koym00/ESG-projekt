@echo off
echo Starting Meteorological Station Analyzer...
echo.
echo The app will be available at: http://localhost:8501
echo Press Ctrl+C to stop the server
echo.
py -m streamlit run streamlit_app.py --server.headless true --server.port 8501
pause