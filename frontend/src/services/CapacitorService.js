import { Capacitor } from '@capacitor/core';
import { Device } from '@capacitor/device';
import { Network } from '@capacitor/network';
import { Haptics, ImpactStyle } from '@capacitor/haptics';
import { StatusBar, Style } from '@capacitor/status-bar';
import { SpeechRecognition } from '@capacitor-community/speech-recognition';
import { TextToSpeech } from '@capacitor-community/text-to-speech';

class CapacitorService {
  constructor() {
    this.isNative = Capacitor.isNativePlatform();
    this.isAndroid = Capacitor.getPlatform() === 'android';
    this.initialized = false;
  }

  async initialize() {
    if (!this.isNative || this.initialized) return;

    try {
      // Initialize device info
      const info = await Device.getInfo();
      console.log('Device info:', info);

      // Initialize network status
      const status = await Network.getStatus();
      console.log('Network status:', status);

      // Setup status bar for Android
      if (this.isAndroid) {
        await StatusBar.setStyle({ style: Style.Dark });
      }

      this.initialized = true;
      console.log('CapacitorService initialized successfully');
    } catch (error) {
      console.error('Error initializing CapacitorService:', error);
    }
  }

  // Speech Recognition (STT)
  async startSpeechRecognition(options = {}) {
    if (!this.isNative) {
      // Fallback to Web Speech API
      return this.startWebSpeechRecognition(options);
    }

    try {
      // Request permissions
      const { speechRecognition } = await SpeechRecognition.requestPermissions();
      if (speechRecognition !== 'granted') {
        throw new Error('Speech recognition permission denied');
      }

      // Check availability
      const { available } = await SpeechRecognition.available();
      if (!available) {
        throw new Error('Speech recognition not available');
      }

      const defaultOptions = {
        language: 'fr-FR',
        maxResults: 1,
        prompt: 'Parlez maintenant...',
        partialResults: true,
        popup: false
      };

      const finalOptions = { ...defaultOptions, ...options };
      
      return new Promise((resolve, reject) => {
        SpeechRecognition.addListener('partialResults', (data) => {
          console.log('Partial results:', data.matches);
          if (options.onPartialResults) {
            options.onPartialResults(data.matches[0] || '');
          }
        });

        SpeechRecognition.addListener('listeningState', (data) => {
          console.log('Listening state:', data.status);
          if (options.onListeningState) {
            options.onListeningState(data.status);
          }
        });

        SpeechRecognition.start(finalOptions)
          .then((result) => {
            resolve(result.matches[0] || '');
          })
          .catch(reject);
      });
    } catch (error) {
      console.error('Native speech recognition error:', error);
      throw error;
    }
  }

  async stopSpeechRecognition() {
    if (!this.isNative) return;
    
    try {
      await SpeechRecognition.stop();
    } catch (error) {
      console.error('Error stopping speech recognition:', error);
    }
  }

  // Text to Speech (TTS)
  async speak(text, options = {}) {
    if (!this.isNative) {
      // Fallback to Web Speech API
      return this.speakWeb(text, options);
    }

    try {
      const defaultOptions = {
        text,
        lang: 'fr-FR',
        rate: 1.0,
        pitch: 1.0,
        volume: 1.0,
        category: 'ambient'
      };

      const finalOptions = { ...defaultOptions, ...options };
      await TextToSpeech.speak(finalOptions);
    } catch (error) {
      console.error('Native TTS error:', error);
      // Fallback to web TTS
      this.speakWeb(text, options);
    }
  }

  async stopSpeaking() {
    if (!this.isNative) {
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      return;
    }

    try {
      await TextToSpeech.stop();
    } catch (error) {
      console.error('Error stopping TTS:', error);
    }
  }

  // Web Speech API fallbacks
  startWebSpeechRecognition(options = {}) {
    return new Promise((resolve, reject) => {
      if (!('webkitSpeechRecognition' in window)) {
        reject(new Error('Web Speech API not supported'));
        return;
      }

      const recognition = new window.webkitSpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = options.language || 'fr-FR';

      recognition.onstart = () => {
        console.log('Web speech recognition started');
        if (options.onListeningState) {
          options.onListeningState('listening');
        }
      };

      recognition.onresult = (event) => {
        const result = event.results[event.results.length - 1];
        const transcript = result.transcript;
        
        if (result.isFinal) {
          resolve(transcript);
        } else if (options.onPartialResults) {
          options.onPartialResults(transcript);
        }
      };

      recognition.onerror = (event) => {
        reject(new Error(`Speech recognition error: ${event.error}`));
      };

      recognition.onend = () => {
        if (options.onListeningState) {
          options.onListeningState('stopped');
        }
      };

      recognition.start();
    });
  }

  speakWeb(text, options = {}) {
    if (!window.speechSynthesis) {
      console.warn('Web Speech Synthesis not supported');
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = options.lang || 'fr-FR';
    utterance.rate = options.rate || 1.0;
    utterance.pitch = options.pitch || 1.0;
    utterance.volume = options.volume || 1.0;

    window.speechSynthesis.speak(utterance);
  }

  // Haptic feedback
  async hapticFeedback(style = ImpactStyle.Medium) {
    if (!this.isNative) return;

    try {
      await Haptics.impact({ style });
    } catch (error) {
      console.error('Haptic feedback error:', error);
    }
  }

  // Network status
  async getNetworkStatus() {
    if (!this.isNative) {
      return { connected: navigator.onLine, connectionType: 'unknown' };
    }

    try {
      return await Network.getStatus();
    } catch (error) {
      console.error('Network status error:', error);
      return { connected: false, connectionType: 'none' };
    }
  }

  // Device info
  async getDeviceInfo() {
    if (!this.isNative) {
      return {
        platform: 'web',
        model: 'Unknown',
        operatingSystem: 'unknown',
        osVersion: 'unknown'
      };
    }

    try {
      return await Device.getInfo();
    } catch (error) {
      console.error('Device info error:', error);
      return null;
    }
  }
}

export default new CapacitorService();