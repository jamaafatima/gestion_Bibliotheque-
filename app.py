from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'ton_secret_key_securise'

# Configuration de la base de données
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="qwerty",
        database="bibliotheque"
    )

# Décorateur pour vérifier l'authentification
def login_required(role=None):
    def decorator(f):
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('Accès refusé : droits insuffisants', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# --------------------
# ROUTES D'AUTHENTIFICATION
# --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Utilisateurs WHERE Email=%s AND Password=%s", (email, password))
        utilisateur = cursor.fetchone()
        db.close()
        
        if utilisateur:
            session['user_id'] = utilisateur['ID']
            session['user_name'] = utilisateur['Nom']
            session['role'] = utilisateur['Role']
            
            flash(f'Bienvenue {utilisateur["Nom"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Identifiants invalides', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Déconnexion réussie', 'success')
    return redirect(url_for('login'))

# --------------------
# ROUTES PRINCIPALES
# --------------------
@app.route('/')
@login_required()
def index():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) AS total_livres FROM Livres")
    total_livres = cursor.fetchone()["total_livres"]

    cursor.execute("SELECT COUNT(*) AS total_utilisateurs FROM Utilisateurs WHERE Role='etudiant'")
    total_utilisateurs = cursor.fetchone()["total_utilisateurs"]

    cursor.execute("SELECT COUNT(*) AS total_emprunts FROM Emprunts WHERE DateRetourReelle IS NULL")
    total_emprunts = cursor.fetchone()["total_emprunts"]

    db.close()
    return render_template('index.html',
                           total_livres=total_livres,
                           total_utilisateurs=total_utilisateurs,
                           total_emprunts=total_emprunts)

# --------------------
# GESTION DES LIVRES
# --------------------
@app.route('/livres')
@login_required()
def livres():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Livres")
    livres = cursor.fetchall()
    db.close()
    return render_template('livres.html', livres=livres)

@app.route('/livres/add', methods=['POST'])
@login_required(role='bibliothecaire')
def add_livre():
    titre = request.form['titre']
    auteur = request.form['auteur']
    isbn = request.form['isbn']
    
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("INSERT INTO Livres (Titre, Auteur, ISBN, Statut) VALUES (%s,%s,%s, 'disponible')", 
                   (titre, auteur, isbn))
    db.commit()
    db.close()
    
    flash('Livre ajouté avec succès', 'success')
    return redirect(url_for('livres'))

@app.route('/livres/delete/<int:id>')
@login_required(role='bibliothecaire')
def delete_livre(id):
    db = get_db_connection()
    cursor = db.cursor()
    
    # Vérifier si le livre est emprunté
    cursor.execute("SELECT Statut FROM Livres WHERE ID=%s", (id,))
    livre = cursor.fetchone()
    
    if livre and livre[0] == 'emprunte':
        flash('Impossible de supprimer : le livre est actuellement emprunté', 'error')
    else:
        cursor.execute("DELETE FROM Livres WHERE ID=%s", (id,))
        db.commit()
        flash('Livre supprimé avec succès', 'success')
    
    db.close()
    return redirect(url_for('livres'))

@app.route('/livres/edit/<int:id>', methods=['GET', 'POST'])
@login_required(role='bibliothecaire')
def edit_livre(id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    if request.method == 'POST':
        titre = request.form['titre']
        auteur = request.form['auteur']
        isbn = request.form['isbn']
        statut = request.form['statut']
        
        cursor.execute("UPDATE Livres SET Titre=%s, Auteur=%s, ISBN=%s, Statut=%s WHERE ID=%s",
                       (titre, auteur, isbn, statut, id))
        db.commit()
        db.close()
        flash('Livre modifié avec succès', 'success')
        return redirect(url_for('livres'))
    else:
        cursor.execute("SELECT * FROM Livres WHERE ID=%s", (id,))
        livre = cursor.fetchone()
        db.close()
        return render_template('edit_livre.html', livre=livre)

# --------------------
# GESTION DES UTILISATEURS
# --------------------
@app.route('/utilisateurs')
@login_required(role='bibliothecaire')
def utilisateurs():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Utilisateurs WHERE Role='etudiant'")
    utilisateurs = cursor.fetchall()
    db.close()
    return render_template('utilisateurs.html', utilisateurs=utilisateurs)

@app.route('/utilisateurs/add', methods=['POST'])
@login_required(role='bibliothecaire')
def add_utilisateur():
    nom = request.form['nom']
    email = request.form['email']
    numero = request.form['numero']
    password = request.form['password']
    
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("INSERT INTO Utilisateurs (Nom, Email, NumeroEtudiant, Role, Password) VALUES (%s,%s,%s, 'etudiant', %s)", 
                   (nom, email, numero, password))
    db.commit()
    db.close()
    
    flash('Étudiant ajouté avec succès', 'success')
    return redirect(url_for('utilisateurs'))

@app.route('/utilisateurs/delete/<int:id>')
@login_required(role='bibliothecaire')
def delete_utilisateur(id):
    db = get_db_connection()
    cursor = db.cursor()
    
    # Vérifier si l'utilisateur a des emprunts en cours
    cursor.execute("SELECT COUNT(*) as nb FROM Emprunts WHERE ID_Utilisateur=%s AND DateRetourReelle IS NULL", (id,))
    emprunts_en_cours = cursor.fetchone()[0]
    
    if emprunts_en_cours > 0:
        flash('Impossible de supprimer : l\'utilisateur a des emprunts en cours', 'error')
    else:
        cursor.execute("DELETE FROM Utilisateurs WHERE ID=%s", (id,))
        db.commit()
        flash('Utilisateur supprimé avec succès', 'success')
    
    db.close()
    return redirect(url_for('utilisateurs'))

# --------------------
# GESTION DES EMPRUNTS
# --------------------
@app.route('/emprunts')
@login_required()
def emprunts():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # Liste des emprunts en cours
    cursor.execute("""
        SELECT e.ID, l.Titre, u.Nom, e.DateEmprunt, e.DateRetourPrevue, e.DateRetourReelle,
               CASE WHEN e.DateRetourPrevue < CURDATE() AND e.DateRetourReelle IS NULL 
                    THEN 'En retard' ELSE 'OK' END as Statut
        FROM Emprunts e
        JOIN Livres l ON e.ID_Livre = l.ID
        JOIN Utilisateurs u ON e.ID_Utilisateur = u.ID
        WHERE e.DateRetourReelle IS NULL
        ORDER BY e.DateRetourPrevue
    """)
    emprunts = cursor.fetchall()

    # Liste des livres disponibles
    cursor.execute("SELECT ID, Titre FROM Livres WHERE Statut='disponible'")
    livres_disponibles = cursor.fetchall()

    # Liste des utilisateurs étudiants
    cursor.execute("SELECT ID, Nom FROM Utilisateurs WHERE Role='etudiant'")
    utilisateurs = cursor.fetchall()

    db.close()
    return render_template('emprunts.html',
                           emprunts=emprunts,
                           livres_disponibles=livres_disponibles,
                           utilisateurs=utilisateurs)

@app.route('/emprunts/add', methods=['POST'])
@login_required(role='bibliothecaire')
def add_emprunt():
    id_livre = request.form['id_livre']
    id_utilisateur = request.form['id_utilisateur']
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # Vérifier que le livre est disponible
    cursor.execute("SELECT Statut FROM Livres WHERE ID=%s", (id_livre,))
    livre = cursor.fetchone()
    if livre['Statut'] == 'emprunte':
        flash('Ce livre est déjà emprunté', 'error')
        db.close()
        return redirect(url_for('emprunts'))
    
    # Vérifier le nombre d'emprunts de l'utilisateur (max 3)
    cursor.execute("SELECT COUNT(*) as nb FROM Emprunts WHERE ID_Utilisateur=%s AND DateRetourReelle IS NULL", 
                   (id_utilisateur,))
    nb_emprunts = cursor.fetchone()['nb']
    
    if nb_emprunts >= 3:
        flash('Cet utilisateur a déjà 3 livres empruntés (maximum autorisé)', 'error')
        db.close()
        return redirect(url_for('emprunts'))
    
    # Créer l'emprunt
    date_emprunt = datetime.now().date()
    date_retour_prevue = date_emprunt + timedelta(days=15)
    
    cursor.execute("INSERT INTO Emprunts (ID_Livre, ID_Utilisateur, DateEmprunt, DateRetourPrevue) VALUES (%s,%s,%s,%s)",
                   (id_livre, id_utilisateur, date_emprunt, date_retour_prevue))
    cursor.execute("UPDATE Livres SET Statut='emprunte' WHERE ID=%s", (id_livre,))
    db.commit()
    db.close()
    
    flash('Emprunt enregistré avec succès', 'success')
    return redirect(url_for('emprunts'))

@app.route('/emprunts/retour/<int:id>')
@login_required(role='bibliothecaire')
def retour_emprunt(id):
    db = get_db_connection()
    cursor = db.cursor()
    
    # Mettre à jour l'emprunt
    cursor.execute("UPDATE Emprunts SET DateRetourReelle = %s WHERE ID = %s", (datetime.now().date(), id))
    
    # Récupérer l'ID du livre et le marquer comme disponible
    cursor.execute("SELECT ID_Livre FROM Emprunts WHERE ID = %s", (id,))
    id_livre = cursor.fetchone()[0]
    cursor.execute("UPDATE Livres SET Statut = 'disponible' WHERE ID = %s", (id_livre,))
    
    db.commit()
    db.close()
    
    flash('Retour enregistré avec succès', 'success')
    return redirect(url_for('emprunts'))

# --------------------
# GESTION DES BIBLIOTHÉCAIRES (Admin uniquement)
# --------------------
@app.route('/admin/bibliothecaires')
@login_required(role='bibliothecaire')
def admin_bibliothecaires():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Utilisateurs WHERE Role='bibliothecaire'")
    bibliothecaires = cursor.fetchall()
    db.close()
    return render_template('admin_bibliothecaires.html', bibliothecaires=bibliothecaires)

@app.route('/admin/bibliothecaires/add', methods=['POST'])
@login_required(role='bibliothecaire')
def add_bibliothecaire():
    nom = request.form['nom']
    email = request.form['email']
    numero = request.form['numero']
    password = request.form['password']
    
    db = get_db_connection()
    cursor = db.cursor()
    
    # Vérifier si l'email existe déjà
    cursor.execute("SELECT COUNT(*) as count FROM Utilisateurs WHERE Email=%s", (email,))
    if cursor.fetchone()[0] > 0:
        flash('Cet email existe déjà dans le système', 'error')
    else:
        cursor.execute("INSERT INTO Utilisateurs (Nom, Email, NumeroEtudiant, Role, Password) VALUES (%s,%s,%s, 'bibliothecaire', %s)", 
                       (nom, email, numero, password))
        db.commit()
        flash('Bibliothécaire ajouté avec succès', 'success')
    
    db.close()
    return redirect(url_for('admin_bibliothecaires'))

@app.route('/admin/bibliothecaires/delete/<int:id>')
@login_required(role='bibliothecaire')
def delete_bibliothecaire(id):
    # Empêcher la suppression si c'est le seul bibliothécaire
    db = get_db_connection()
    cursor = db.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM Utilisateurs WHERE Role='bibliothecaire'")
    nb_bibliothecaires = cursor.fetchone()[0]
    
    if nb_bibliothecaires <= 1:
        flash('Impossible de supprimer : il doit y avoir au moins un bibliothécaire', 'error')
    elif session['user_id'] == id:
        flash('Vous ne pouvez pas supprimer votre propre compte', 'error')
    else:
        cursor.execute("DELETE FROM Utilisateurs WHERE ID=%s", (id,))
        db.commit()
        flash('Bibliothécaire supprimé avec succès', 'success')
    
    db.close()
    return redirect(url_for('admin_bibliothecaires'))

# --------------------
# RECHERCHE
# --------------------
@app.route('/recherche', methods=['GET', 'POST'])
@login_required()
def recherche():
    livres = []
    if request.method == 'POST':
        motcle = request.form['motcle']
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Livres WHERE Titre LIKE %s OR Auteur LIKE %s",
                       ('%' + motcle + '%', '%' + motcle + '%'))
        livres = cursor.fetchall()
        db.close()
    return render_template('recherche.html', livres=livres)

if __name__ == '__main__':
    app.run(debug=True)