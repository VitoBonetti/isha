// Helper to convert base64 to ArrayBuffer
const b64ToArrayBuffer = (b64: string) => {
  const binaryString = window.atob(b64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
};

// Helper to convert ArrayBuffer to base64
const arrayBufferToB64 = (buffer: ArrayBuffer) => {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
};

// Convert PEM format to CryptoKey
export const importPublicKey = async (pem: string): Promise<CryptoKey> => {
  const b64 = pem.replace(/(-----(BEGIN|END) PUBLIC KEY-----|\n|\r)/g, '');
  return await window.crypto.subtle.importKey(
    "spki",
    b64ToArrayBuffer(b64),
    { name: "RSA-OAEP", hash: "SHA-256" },
    true,
    ["encrypt"]
  );
};

export const importPrivateKey = async (pem: string): Promise<CryptoKey> => {
  const b64 = pem.replace(/(-----(BEGIN|END) PRIVATE KEY-----|\n|\r)/g, '');
  return await window.crypto.subtle.importKey(
    "pkcs8",
    b64ToArrayBuffer(b64),
    { name: "RSA-OAEP", hash: "SHA-256" },
    true,
    ["decrypt"]
  );
};

// Generate a random 256-bit AES-GCM Key (The DEK)
export const generateAesKey = async (): Promise<CryptoKey> => {
  return await window.crypto.subtle.generateKey(
    { name: "AES-GCM", length: 256 },
    true,
    ["encrypt", "decrypt"]
  );
};

// Encrypt the Note using AES-GCM
export const encryptNote = async (text: string, aesKey: CryptoKey) => {
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const encoded = new TextEncoder().encode(text);
  const ciphertext = await window.crypto.subtle.encrypt({ name: "AES-GCM", iv: iv }, aesKey, encoded);
  return JSON.stringify({
    iv: arrayBufferToB64(iv),
    ciphertext: arrayBufferToB64(ciphertext)
  });
};

// Decrypt the Note using AES-GCM
export const decryptNote = async (encryptedDataStr: string, aesKey: CryptoKey) => {
  const data = JSON.parse(encryptedDataStr);
  const iv = b64ToArrayBuffer(data.iv);
  const ciphertext = b64ToArrayBuffer(data.ciphertext);
  const decrypted = await window.crypto.subtle.decrypt({ name: "AES-GCM", iv: new Uint8Array(iv) }, aesKey, ciphertext);
  return new TextDecoder().decode(decrypted);
};

// Encrypt the AES Key with a User's RSA Public Key
export const wrapKeyWithRSA = async (aesKey: CryptoKey, rsaPubKey: CryptoKey) => {
  const rawAesKey = await window.crypto.subtle.exportKey("raw", aesKey);
  const encryptedKey = await window.crypto.subtle.encrypt({ name: "RSA-OAEP" }, rsaPubKey, rawAesKey);
  return arrayBufferToB64(encryptedKey);
};

// Decrypt the AES Key with the User's RSA Private Key
export const unwrapKeyWithRSA = async (encryptedKeyB64: string, rsaPrivKey: CryptoKey) => {
  const encryptedKeyBuffer = b64ToArrayBuffer(encryptedKeyB64);
  const rawAesKey = await window.crypto.subtle.decrypt({ name: "RSA-OAEP" }, rsaPrivKey, encryptedKeyBuffer);
  return await window.crypto.subtle.importKey("raw", rawAesKey, { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
};

// Helper to chunk Base64 strings into 64-character lines (PEM format standard)
const formatPEM = (b64: string, type: 'PUBLIC' | 'PRIVATE') => {
  const lines = b64.match(/.{1,64}/g) || [];
  return `-----BEGIN ${type} KEY-----\n${lines.join('\n')}\n-----END ${type} KEY-----`;
};

// Generate the RSA-OAEP 4096-bit Key Pair in the browser
export const generateRSAKeyPair = async () => {
  const keyPair = await window.crypto.subtle.generateKey(
    {
      name: "RSA-OAEP",
      modulusLength: 4096, // Enterprise standard
      publicExponent: new Uint8Array([1, 0, 1]), // 65537
      hash: "SHA-256",
    },
    true, // Must be true so we can export them!
    ["encrypt", "decrypt"]
  );

  // 1. Export Public Key (SPKI)
  const pubBuffer = await window.crypto.subtle.exportKey("spki", keyPair.publicKey);
  const pubB64 = arrayBufferToB64(pubBuffer);
  const pubPem = formatPEM(pubB64, 'PUBLIC');

  // 2. Export Private Key (PKCS#8)
  const privBuffer = await window.crypto.subtle.exportKey("pkcs8", keyPair.privateKey);
  const privB64 = arrayBufferToB64(privBuffer);
  const privPem = formatPEM(privB64, 'PRIVATE');

  return { publicKey: pubPem, privateKey: privPem };
};