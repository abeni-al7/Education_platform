import os
from flask import Flask, render_template, request, flash, redirect, url_for, session, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, SelectField, TextAreaField, PasswordField, validators, FileField
from passlib.hash import sha256_crypt
from functools import wraps

app = Flask(__name__, static_url_path='/static')
app.config.from_pyfile('config.py')

mysql = MySQL(app)

@app.route('/')
def index():
        return render_template('index.html')

class SignUpForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=100)])
    email = StringField('Email', [validators.Length(min=6, max=100)])
    role = SelectField('Role', choices=[('Student', 'Student'), ('Teacher', 'Teacher') ])
    username = StringField('Username', [validators.Length(min=4, max=100)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')

def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Please login', 'info')
            return redirect(url_for('login'))
    return wrap

@app.route('/admin_dashboard')
@is_logged_in
def admin_dashboard():
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    cur.execute("SELECT * FROM courseware")
    courses = cur.fetchall()
    cur.close()
    return render_template('admin_dashboard.html', users=users, courses=courses)
    return None


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignUpForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        role = form.role.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM users WHERE username=%s", [username])
        if result > 0:
            flash('The entered username already exists.Please try using another username.', 'info')
            return redirect(url_for('signup'))
        else:
            cur.execute("INSERT INTO users(name , email, role, username, password) VALUES(%s, %s, %s, %s, %s)",
                    (name, email, role, username, password))
            mysql.connection.commit()
            cur.close()
            flash('You are now registered and can log in', 'success')
            return redirect(url_for('login'))
    return render_template('signUp.html', form=form)

class LoginForm(Form):
    username = StringField('Username', [validators.Length(min=4, max=100)])
    password = PasswordField('Password', [
        validators.DataRequired(),
    ])


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        username = form.username.data
        password_input = form.password.data

        if username == 'admin' and password_input == 'admin123':
            session['logged_in'] = True
            session['username'] = username
            session['role'] = 'Admin'
            session['is_admin'] = True
            flash('You are now logged in', 'success')
            return redirect(url_for('admin_dashboard'))

        cur = mysql.connection.cursor()

        result = cur.execute(
            "SELECT * FROM users WHERE username = %s", [username])

        if result > 0:
            data = cur.fetchone()
            userID = data['id']
            password = data['password']
            role = data['role']

            if sha256_crypt.verify(password_input, password):
                session['logged_in'] = True
                session['username'] = username
                session['role'] = role
                session['userID'] = userID
                flash('You are now logged in', 'success')
                return redirect(url_for('index'))
            else:
                error = 'Invalid Password'
                return render_template('login.html', form=form, error=error)

            cur.close()

        else:
            error = 'Username not found'
            return render_template('login.html', form=form, error=error)

    return render_template('login.html', form=form)


def is_teacher(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session['role'] == 'Teacher':
            return f(*args, **kwargs)
        else:
            flash('You are not a Teacher', 'danger')
            return redirect(url_for('add_complaint'))
    return wrap

def is_student(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session['role'] == 'Student':
            return f(*args, **kwargs)
        else:
            flash('You are not a Student', 'danger')
            return redirect(url_for('add_complaint'))
    return wrap

@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@is_logged_in
@is_teacher
def dashboard():
    cur = mysql.connection.cursor()
    result = cur.execute(f"SELECT * FROM courseware WHERE user_id = {session['userID']}")
    courses = cur.fetchall()
    if result > 0:
        return render_template('dashboard.html', courses=courses)
    else:
        msg = 'No courses have been created'
        return render_template('dashboard.html', msg=msg)
    cur.close()

@app.route('/all_courses')
@is_logged_in
@is_student
def stud_courses():
    cur = mysql.connection.cursor()
    result = cur.execute(f"SELECT * FROM courseware")
    courses = cur.fetchall()
    if result > 0:
        return render_template('all_courses.html', courses=courses)
    else:
        msg = 'No courses have been created'
        return render_template('index.html', msg=msg)
    cur.close()

class CourseForm(Form):
    title = StringField('Title', [validators.Length(min=1, max=200)])
    subject = StringField('Subject', [validators.Length(min=1, max=200)])
    description = StringField('Description', [validators.Length(min=1, max=200)])
    body = TextAreaField('Body', [validators.Length(min=20)])


@app.route('/add_course', methods=['GET', 'POST'])
@is_logged_in
@is_teacher
def add_course():
    form = CourseForm(request.form)
    if request.method == 'POST' and form.validate():
        title = form.title.data
        subject = form.subject.data
        description = form.description.data
        body = form.body.data

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO courseware(user_id, title, subject, description, body, author) VALUES(%s, %s, %s, %s, %s, %s)",
                    (session['userID'], title, subject, description, body, session['username']))

        mysql.connection.commit()
        cur.close()

        flash('Your courseware has been registered', 'success')
        if session['role'] == 'Teacher':
            return redirect(url_for('dashboard'))
    return render_template('add_course.html', form=form)

@app.route('/review_course/<string:id>', methods=['GET', 'POST'])
@is_logged_in
@is_teacher
def review_course(id):
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM courseware WHERE id = %s", [id])
    courses = cur.fetchall()
    if result > 0:
        return render_template('detail_page.html', courses=courses)
    else:
        msg = 'The Course is empty and cannot be reviewed'
        return render_template('dashboard.html', msg=msg)
    cur.close()

@app.route('/entered_course/<string:title>', methods=['GET', 'POST'])
@is_logged_in
def entered_course(title):
    cur = mysql.connection.cursor()
    result = cur.execute("""SELECT
                            users.name,
                            student_courses.id,
                            student_courses.status,
                            student_courses.enroll_date,
                            courseware.id,
                            courseware.title,
                            courseware.description,
                            courseware.body,
                            courseware.subject,
                            courseware.issue_date,
                            courseware.author
                            FROM student_courses
                            INNER JOIN courseware on courseware.id = student_courses.courseware_id
                            INNER JOIN users on users.id = student_courses.user_id
                            WHERE title = %s""", [title])
    courses = cur.fetchall()
    if result > 0:
        return render_template('detail_page.html', courses=courses)
    else:
        msg = 'The Course is empty and cannot be reviewed'
        return render_template('index.html', msg=msg)
    cur.close()

@app.route('/enrolled_students/<string:id>', methods=['GET', 'POST'])
@is_logged_in
@is_teacher
def enrolled_students(id):
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT COUNT(ID) from course.student_courses WHERE status = 'open' and courseware_id = %s", [id])
    data = cur.fetchone()
    total = data['COUNT(ID)']
    if result>0:
        return render_template('total.html', total=total)
    else:
        msg = 'No one has enrolled for this course yet!'
        return render_template('dashboard.html', msg=msg)
    cur.close()

@app.route('/enrolled/<string:id>', methods=['GET', 'POST'])
@is_logged_in
@is_student
def enrolled(id):
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO student_courses(user_id, courseware_id) VALUES(%s, %s)",
                    (session['userID'], [id]))
    mysql.connection.commit()
    cur.close()
    if session['role'] == 'Student':
        flash('You are now enrolled for the course', 'success')
        return redirect(url_for('my_courses'))
    return render_template('all_courses.html')

@app.route('/my_courses')
@is_logged_in
@is_student
def my_courses():
    cur = mysql.connection.cursor()
    result = cur.execute(f"""
                            SELECT
                            users.name,
                            student_courses.id,
                            student_courses.status,
                            student_courses.enroll_date,
                            courseware.id,
                            courseware.title,
                            courseware.description,
                            courseware.subject,
                            courseware.issue_date,
                            courseware.author
                            FROM student_courses
                            INNER JOIN courseware on courseware.id = student_courses.courseware_id
                            INNER JOIN users on users.id = student_courses.user_id 
                            WHERE users.id = {session['userID']}
                            """)
    courses = cur.fetchall()
    if result > 0:
        return render_template('my_courses.html', courses=courses)
    else:
        msg = 'You have not enrolled in any of the courses'
        return render_template('all_courses.html', msg=msg)
    cur.close()

@app.route('/edit_course/<string:id>', methods=['GET', 'POST'])
@is_logged_in
@is_teacher
def edit_course(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM courseware WHERE id = %s", [id])
    course = cur.fetchone()
    cur.close()
    form = CourseForm(request.form)
    form.title.data = course['title']
    form.subject.data = course['subject']
    form.description.data = course['description']
    form.body.data = course['body']
    if request.method == 'POST' and form.validate():
        title = request.form['title']
        subject = request.form['subject']
        description = request.form['description']
        body = request.form['body']

        cur = mysql.connection.cursor()

        cur.execute ("UPDATE courseware SET title=%s, subject=%s, description=%s, body=%s WHERE id=%s",(title, subject, description, body, id))

        mysql.connection.commit()

        #Close connection
        cur.close()

        flash('Course Updated', 'success')

        return redirect(url_for('dashboard'))

    return render_template('edit_course.html', form=form)


@app.route('/delete_course/<string:id>', methods=['POST'])
@is_logged_in
@is_teacher
def delete_course(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Execute
    cur.execute("DELETE FROM courseware WHERE id = %s", [id])

    # Commit to DB
    mysql.connection.commit()

    #Close connection
    cur.close()

    flash('Course Deleted', 'success')

    return redirect(url_for('dashboard'))

@app.route('/unenroll_course/<string:id>', methods=['POST'])
@is_logged_in
@is_student
def unenroll_course(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Execute
    cur.execute("DELETE FROM student_courses WHERE id = %s", [id])

    # Commit to DB
    mysql.connection.commit()

    #Close connection
    cur.close()

    flash('Unenrolled from course', 'success')

    return redirect(url_for('my_courses'))

@app.route('/admin/add_course', methods=['GET', 'POST'])
@is_logged_in
def admin_add_course():
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    form = CourseForm(request.form)
    if request.method == 'POST' and form.validate():
        title = form.title.data
        subject = form.subject.data
        description = form.description.data
        body = form.body.data

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO courseware(user_id, title, subject, description, body, author) VALUES(%s, %s, %s, %s, %s, %s)",
                    (session['userID'], title, subject, description, body, session['username']))

        mysql.connection.commit()
        cur.close()

        flash('Your courseware has been registered', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_add_course.html', form=form)

@app.route('/admin/edit_course/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def admin_edit_course(id):
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM courseware WHERE id = %s", [id])
    course = cur.fetchone()
    cur.close()
    form = CourseForm(request.form)
    form.title.data = course['title']
    form.subject.data = course['subject']
    form.description.data = course['description']
    form.body.data = course['body']
    if request.method == 'POST' and form.validate():
        title = request.form['title']
        subject = request.form['subject']
        description = request.form['description']
        body = request.form['body']

        cur = mysql.connection.cursor()

        cur.execute ("UPDATE courseware SET title=%s, subject=%s, description=%s, body=%s WHERE id=%s",(title, subject, description, body, id))

        mysql.connection.commit()

        #Close connection
        cur.close()

        flash('Course Updated', 'success')

        return redirect(url_for('admin_dashboard'))

    return render_template('admin_edit_course.html', form=form)

@app.route('/admin/delete_course/<string:id>', methods=['POST'])
@is_logged_in
def admin_delete_course(id):
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    # Create cursor
    cur = mysql.connection.cursor()

    # Execute
    cur.execute("DELETE FROM courseware WHERE id = %s", [id])

    # Commit to DB
    mysql.connection.commit()

    #Close connection
    cur.close()

    flash('Course Deleted', 'success')

    return redirect(url_for('admin_dashboard'))

class StudentForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=100)])
    email = StringField('Email', [validators.Length(min=6, max=50)])

@app.route('/admin/add_student', methods=['GET', 'POST'])
@is_logged_in
def admin_add_student():
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    form = StudentForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        password = sha256_crypt.encrypt(str(form.password.data))

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users(name, email, password, role) VALUES(%s, %s, %s, 'student')", (name, email, password))
        mysql.connection.commit()
        cur.close()

        flash('Student added', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_student.html', form=form)

@app.route('/admin/edit_student/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def admin_edit_student(id):
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))

    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM users WHERE id = %s AND role = 'student'", [id])
    student = cur.fetchone()
    cur.close()

    form = StudentForm(request.form)
    form.name.data = student['name']
    form.email.data = student['email']

    if request.method == 'POST' and form.validate():
        name = request.form['name']
        email = request.form['email']

        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET name=%s, email=%s WHERE id=%s AND role='student'", (name, email, id))
        mysql.connection.commit()
        cur.close()

        flash('Student updated', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_student.html', form=form)

@app.route('/admin/delete_student/<string:id>', methods=['POST'])
@is_logged_in
def admin_delete_student(id):
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s AND role = 'student'", [id])
    mysql.connection.commit()
    cur.close()

    flash('Student deleted', 'success')
    return redirect(url_for('admin_dashboard'))

class TeacherForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=100)])
    email = StringField('Email', [validators.Length(min=6, max=50)])

@app.route('/admin/add_teacher', methods=['GET', 'POST'])
@is_logged_in
def admin_add_teacher():
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    form = TeacherForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        password = sha256_crypt.encrypt(str(form.password.data))

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users(name, email, password, role) VALUES(%s, %s, %s, 'teacher')", (name, email, password))
        mysql.connection.commit()
        cur.close()

        flash('Teacher added', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_teacher.html', form=form)

@app.route('/admin/edit_teacher/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def admin_edit_teacher(id):
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))

    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM users WHERE id = %s AND role = 'teacher'", [id])
    teacher = cur.fetchone()
    cur.close()

    form = TeacherForm(request.form)
    form.name.data = teacher['name']
    form.email.data = teacher['email']

    if request.method == 'POST' and form.validate():
        name = request.form['name']
        email = request.form['email']

        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET name=%s, email=%s WHERE id=%s AND role='teacher'", (name, email, id))
        mysql.connection.commit()
        cur.close()

        flash('Teacher updated', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_teacher.html', form=form)

@app.route('/admin/delete_teacher/<string:id>', methods=['POST'])
@is_logged_in
def admin_delete_teacher(id):
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s AND role = 'teacher'", [id])
    mysql.connection.commit()
    cur.close()

    flash('Teacher deleted', 'success')
    return redirect(url_for('admin_dashboard'))

class AssignmentForm(Form):
    title = StringField('Title', [validators.Length(min=1, max=200)])
    description = TextAreaField('Description', [validators.Length(min=1)])
    file = FileField('Assignment File', [validators.DataRequired()])

@app.route('/add_assignment/<string:course_id>', methods=['GET', 'POST'])
@is_logged_in
@is_teacher
def add_assignment(course_id):
    form = AssignmentForm(request.form)
    if request.method == 'POST' and form.validate():
        title = form.title.data
        description = form.description.data
        file = request.files['file']
        file_path = os.path.join('uploads', file.filename)
        file.save(file_path)

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO assignments(course_id, title, description, file_path) VALUES(%s, %s, %s, %s)", (course_id, title, description, file_path))
        mysql.connection.commit()
        cur.close()

        flash('Assignment added', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_assignment.html', form=form)

@app.route('/submit_assignment/<string:assignment_id>', methods=['GET', 'POST'])
@is_logged_in
@is_student
def submit_assignment(assignment_id):
    if request.method == 'POST':
        file = request.files['file']
        file_path = os.path.join('uploads', file.filename)
        file.save(file_path)

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO submissions(assignment_id, student_id, file_path) VALUES(%s, %s, %s)", (assignment_id, session['userID'], file_path))
        mysql.connection.commit()
        cur.close()

        flash('Assignment submitted', 'success')
        return redirect(url_for('my_courses'))

    return render_template('submit_assignment.html')

@app.route('/grade_assignment/<string:submission_id>', methods=['GET', 'POST'])
@is_logged_in
@is_teacher
def grade_assignment(submission_id):
    if request.method == 'POST':
        grade = request.form['grade']

        cur = mysql.connection.cursor()
        cur.execute("UPDATE submissions SET grade = %s WHERE id = %s", (grade, submission_id))
        mysql.connection.commit()
        cur.close()

        flash('Assignment graded', 'success')
        return redirect(url_for('dashboard'))

    return render_template('grade_assignment.html')



if __name__ == '__main__':
    app.run(debug=True)