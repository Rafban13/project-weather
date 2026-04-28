# 🌤️ Project Weather

> Indoor & Outdoor Weather Monitoring System
> Cloud and Advanced Analytics — Spring 2026

## 👥 Team

- **Raffaele-Alban Bakija** ([@Rafban13](https://github.com/Rafban13)) — *role TBD*
- **Arlind Kadriu** ([@63didi](https://github.com/63didi)) — *role TBD*

## 📋 Project Overview

This project implements an indoor/outdoor weather monitoring system using an M5Stack IoT device equipped with environmental sensors. The system collects indoor measurements (temperature, humidity, air quality) and combines them with outdoor weather data fetched from external APIs. All data is stored in Google BigQuery and visualized through both an on-device interface and a cloud-based Streamlit dashboard.

The device also features voice announcements (Text-to-Speech), AI-generated weather descriptions (Vertex AI / Gemini), and motion-triggered interactions.

## 🏗️ Architecture

The project follows a 3-tier architecture:

- **Data layer**: Google BigQuery (sensor data + historical weather)
- **Middleware**: Flask service deployed on Google Cloud Run
- **UI layer**:
  - On-device: M5Stack Core2 (Python / UIFlow)
  - Cloud: Streamlit dashboard deployed on Google Cloud Run

## 📁 Repository Structure