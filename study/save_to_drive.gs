/**
 * Google Apps Script that receives each participant's CSV from the study page
 * and saves it as a file in one private Google Drive folder.
 *
 * Setup (once, about 5 minutes):
 *  1. Create a folder in Google Drive, e.g. "VCF study data". Open it and copy
 *     the folder ID from the address bar (the part after /folders/).
 *  2. Go to https://script.google.com, click New project, delete the sample
 *     code and paste this whole file. Put the folder ID in FOLDER_ID below.
 *  3. Click Deploy > New deployment > type "Web app".
 *       Execute as: Me
 *       Who has access: Anyone
 *     Click Deploy and allow the permissions it asks for.
 *  4. Copy the Web app URL (ends in /exec) into CONFIG.SAVE_URL in
 *     docs/experiment.js.
 *
 * "Anyone" only means anyone can send data to this script. Nobody but you can
 * read the folder. Files are named <participant>_<session>.csv; a name that
 * already exists gets a timestamp so nothing is overwritten.
 */

const FOLDER_ID = "PASTE_FOLDER_ID_HERE";
const MAX_BYTES = 2 * 1024 * 1024; // one participant's data is about 0.3 MB

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    const data = String(body.data || "");
    if (!data || data.length > MAX_BYTES) return reply({ ok: false, error: "empty or too large" });
    let name = String(body.filename || "unnamed.csv").replace(/[^A-Za-z0-9_.-]/g, "_").slice(0, 120);
    if (!name.endsWith(".csv")) name += ".csv";
    const folder = DriveApp.getFolderById(FOLDER_ID);
    if (folder.getFilesByName(name).hasNext()) name = name.replace(/\.csv$/, `_${Date.now()}.csv`);
    folder.createFile(name, data, MimeType.CSV);
    return reply({ ok: true, file: name });
  } catch (err) {
    return reply({ ok: false, error: String(err) });
  }
}

function doGet() {
  return reply({ ok: true, message: "VCF study endpoint is running" });
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
