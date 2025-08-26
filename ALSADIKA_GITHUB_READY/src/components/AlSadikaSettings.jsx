import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Switch } from "./ui/switch";
import { Button } from "./ui/button";
import { Label } from "./ui/label";
import { Alert, AlertDescription } from "./ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Separator } from "./ui/separator";
import { Shield, Mic, Smartphone, AlertTriangle, Settings } from 'lucide-react';
import CapacitorService from '../services/CapacitorService';

const AlSadikaSettings = ({ isOpen, onClose }) => {
  const [settings, setSettings] = useState({
    // Mode Basique (toujours activé)
    voiceRecognition: true,
    textToSpeech: true,
    offlineMode: true,
    hotMic: false,
    
    // Mode Contrôle Total (opt-in)
    controlMode: false,
    accessibilityService: false,
    systemOverlay: false,
    usageStats: false,
    notifications: false,
    
    // Configuration
    activationPhrase: "Bismillah, contrôle total ON",
    stopPhrase: "Contrôle total OFF"
  });

  const [deviceInfo, setDeviceInfo] = useState(null);
  const [networkStatus, setNetworkStatus] = useState(null);
  const [isNative, setIsNative] = useState(false);

  useEffect(() => {
    initializeSettings();
  }, []);

  const initializeSettings = async () => {
    try {
      await CapacitorService.initialize();
      setIsNative(CapacitorService.isNative);
      
      if (CapacitorService.isNative) {
        const info = await CapacitorService.getDeviceInfo();
        const network = await CapacitorService.getNetworkStatus();
        setDeviceInfo(info);
        setNetworkStatus(network);
      }

      // Load saved settings from localStorage
      const savedSettings = localStorage.getItem('alsadika-settings');
      if (savedSettings) {
        setSettings(prev => ({ ...prev, ...JSON.parse(savedSettings) }));
      }
    } catch (error) {
      console.error('Error initializing settings:', error);
    }
  };

  const saveSettings = (newSettings) => {
    setSettings(newSettings);
    localStorage.setItem('alsadika-settings', JSON.stringify(newSettings));
  };

  const handleToggle = (key, value) => {
    const newSettings = { ...settings, [key]: value };
    
    // Special handling for control mode
    if (key === 'controlMode' && value) {
      // Show confirmation dialog for enabling control mode
      if (window.confirm(`ATTENTION: Vous allez activer le mode "Contrôle Total".\n\nCeci permettra à Al Sâdika de:\n- Automatiser les interactions avec votre téléphone\n- Accéder aux informations d'usage des applications\n- Afficher des éléments par-dessus d'autres applications\n\nContinuer?`)) {
        if (isNative) {
          // On native, redirect to system settings
          redirectToSystemSettings();
        }
        saveSettings(newSettings);
      } else {
        return; // Cancel the change
      }
    } else {
      saveSettings(newSettings);
    }
  };

  const redirectToSystemSettings = () => {
    // This would call native Android intents
    if (CapacitorService.isAndroid) {
      // In a real implementation, we'd call native methods to open:
      // - Accessibility settings
      // - Usage stats permission
      // - System overlay permission
      console.log('Redirecting to Android system settings...');
    }
  };

  const testVoiceRecognition = async () => {
    try {
      await CapacitorService.hapticFeedback();
      const result = await CapacitorService.startSpeechRecognition({
        language: 'fr-FR',
        prompt: 'Test de reconnaissance vocale...',
        onListeningState: (state) => {
          console.log('Listening state:', state);
        }
      });
      
      if (result) {
        await CapacitorService.speak(`J'ai entendu: ${result}`);
      }
    } catch (error) {
      console.error('Voice recognition test failed:', error);
      alert('Erreur lors du test de reconnaissance vocale: ' + error.message);
    }
  };

  const testTextToSpeech = async () => {
    try {
      await CapacitorService.hapticFeedback();
      await CapacitorService.speak("Je suis Al Sâdika, votre assistante véridique et souveraine.");
    } catch (error) {
      console.error('TTS test failed:', error);
      alert('Erreur lors du test de synthèse vocale: ' + error.message);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Paramètres Al Sâdika
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Device Info */}
          {isNative && deviceInfo && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Informations de l'appareil</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                <div className="grid grid-cols-2 gap-2">
                  <div>Plateforme: {deviceInfo.platform}</div>
                  <div>Modèle: {deviceInfo.model}</div>
                  <div>OS: {deviceInfo.operatingSystem} {deviceInfo.osVersion}</div>
                  <div>Réseau: {networkStatus?.connected ? 'Connecté' : 'Hors ligne'}</div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Mode Basique */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-green-600" />
                Mode Basique (Toujours actif)
              </CardTitle>
              <CardDescription>
                Fonctionnalités de base pour le chat vocal avec Al Sâdika
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="voice-recognition">Reconnaissance vocale</Label>
                  <p className="text-sm text-muted-foreground">Convertir votre voix en texte</p>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    id="voice-recognition"
                    checked={settings.voiceRecognition}
                    onCheckedChange={(value) => handleToggle('voiceRecognition', value)}
                  />
                  <Button size="sm" variant="outline" onClick={testVoiceRecognition}>
                    Test
                  </Button>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="text-to-speech">Synthèse vocale</Label>
                  <p className="text-sm text-muted-foreground">Al Sâdika parle à voix haute</p>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    id="text-to-speech"
                    checked={settings.textToSpeech}
                    onCheckedChange={(value) => handleToggle('textToSpeech', value)}
                  />
                  <Button size="sm" variant="outline" onClick={testTextToSpeech}>
                    Test
                  </Button>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="offline-mode">Mode hors ligne</Label>
                  <p className="text-sm text-muted-foreground">Fonctionnement sans internet (noyau local)</p>
                </div>
                <Switch
                  id="offline-mode"
                  checked={settings.offlineMode}
                  onCheckedChange={(value) => handleToggle('offlineMode', value)}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="hot-mic">Écoute continue (Hot Mic)</Label>
                  <p className="text-sm text-muted-foreground">Service en arrière-plan avec notification</p>
                </div>
                <Switch
                  id="hot-mic"
                  checked={settings.hotMic}
                  onCheckedChange={(value) => handleToggle('hotMic', value)}
                />
              </div>
            </CardContent>
          </Card>

          <Separator />

          {/* Mode Contrôle Total */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Smartphone className="h-5 w-5 text-orange-600" />
                Mode Contrôle Total (Opt-in)
              </CardTitle>
              <CardDescription>
                Automatisation avancée du téléphone - Activation manuelle requise
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!settings.controlMode && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    Le mode Contrôle Total est désactivé. Activez-le pour permettre à Al Sâdika d'automatiser votre téléphone.
                  </AlertDescription>
                </Alert>
              )}

              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="control-mode">Activer le Contrôle Total</Label>
                  <p className="text-sm text-muted-foreground">
                    Phrase d'activation: "{settings.activationPhrase}"
                  </p>
                </div>
                <Switch
                  id="control-mode"
                  checked={settings.controlMode}
                  onCheckedChange={(value) => handleToggle('controlMode', value)}
                />
              </div>

              {settings.controlMode && (
                <>
                  <div className="ml-4 space-y-3 border-l-2 border-orange-200 pl-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label htmlFor="accessibility-service">Service d'accessibilité</Label>
                        <p className="text-sm text-muted-foreground">Automatisation UI (clic, scroll, saisie)</p>
                      </div>
                      <Switch
                        id="accessibility-service"
                        checked={settings.accessibilityService}
                        onCheckedChange={(value) => handleToggle('accessibilityService', value)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <Label htmlFor="system-overlay">Superposition système</Label>
                        <p className="text-sm text-muted-foreground">Bulles d'action et guidage visuel</p>
                      </div>
                      <Switch
                        id="system-overlay"
                        checked={settings.systemOverlay}
                        onCheckedChange={(value) => handleToggle('systemOverlay', value)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <Label htmlFor="usage-stats">Statistiques d'usage</Label>
                        <p className="text-sm text-muted-foreground">Contexte des applications utilisées</p>
                      </div>
                      <Switch
                        id="usage-stats"
                        checked={settings.usageStats}
                        onCheckedChange={(value) => handleToggle('usageStats', value)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <Label htmlFor="notifications">Notifications actionnables</Label>
                        <p className="text-sm text-muted-foreground">Réponses directes et actions contextuelles</p>
                      </div>
                      <Switch
                        id="notifications"
                        checked={settings.notifications}
                        onCheckedChange={(value) => handleToggle('notifications', value)}
                      />
                    </div>
                  </div>

                  <Alert>
                    <Shield className="h-4 w-4" />
                    <AlertDescription>
                      <strong>Sécurité:</strong> Toutes les actions passent par le noyau Al Sâdika. 
                      Aucune clé API LLM n'est stockée dans l'application. 
                      Désactivation immédiate avec "{settings.stopPhrase}".
                    </AlertDescription>
                  </Alert>
                </>
              )}
            </CardContent>
          </Card>

          {/* Journal des actions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Journal noyau</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground">
                <div>• Activations/désactivations: Journalisées</div>
                <div>• PII (données personnelles): Exclu par défaut</div>
                <div>• Filtrage éthique: Obligatoire côté serveur</div>
                <div>• Souveraineté: Noyau gouverne, pas le LLM externe</div>
              </div>
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="flex justify-between">
            <Button variant="outline" onClick={onClose}>
              Fermer
            </Button>
            <Button 
              onClick={() => {
                localStorage.removeItem('alsadika-settings');
                setSettings({
                  voiceRecognition: true,
                  textToSpeech: true,
                  offlineMode: true,
                  hotMic: false,
                  controlMode: false,
                  accessibilityService: false,
                  systemOverlay: false,
                  usageStats: false,
                  notifications: false,
                  activationPhrase: "Bismillah, contrôle total ON",
                  stopPhrase: "Contrôle total OFF"
                });
              }}
              variant="destructive"
            >
              Réinitialiser
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AlSadikaSettings;