folder("Whanos base images") {
	description("The base images of whanos.")
}

available_languages = ['c', 'java', 'javascript', 'python', 'befunge']

for (language in available_languages) {
    freeStyleJob("Whanos base images/whanos-${language}") {
        steps {
            shell("docker build /images/${language} -f /images/${language}/Dockerfile.base -t whanos/${language}:latest")
        }
    }
}

freeStyleJob("Whanos base images/Build all base images") {
	publishers {
		downstream(
			available_languages.collect { language -> "Whanos base images/whanos-${language}" }
		)
	}
}

folder("Projects") {
	description("The projects of whanos.")
}

freeStyleJob("link-project") {
    parameters {
        stringParam('GIT_REPOSITORY_URL', '', 'Git repository URL')
        stringParam('PROJECT_NAME', '', 'Name of the project to link')
    }

    steps {
        dsl {
            text('''
                freeStyleJob("Projects/$PROJECT_NAME") {
                    scm {
                        git {
                            remote {
                                url('$REPOSITORY_URL')
                            }
                        }
                    }
                    triggers {
                        scm('* * * * *')
                    }
                    wrappers {
                        preBuildCleanup()
                    }
                    steps {
                        shell("""
                             if [ -f Dockerfile ]; then
                                echo "Custom Dockerfile detected - Using it directly"
                                docker build -t "$PROJECT_NAME" .
                            else
                                # Détection du langage
                                if [ -f Makefile ]; then
                                    echo "C project detected"
                                    cp /images/c/Dockerfile.template Dockerfile
                                    docker build -t "$PROJECT_NAME" .
                                elif [ -f pom.xml ]; then
                                    echo "Java project detected"
                                    cp /images/java/Dockerfile.template Dockerfile
                                    docker build -t "$PROJECT_NAME" .
                                elif [ -f package.json ]; then
                                    echo "JavaScript project detected"
                                    cp /images/javascript/Dockerfile.template Dockerfile
                                    docker build -t "$PROJECT_NAME" .
                                elif [ -f requirements.txt ]; then
                                    echo "Python project detected"
                                    cp /images/python/Dockerfile.template Dockerfile
                                    docker build -t "$PROJECT_NAME" .
                                elif [ -f *.bf ]; then
                                    echo "Befunge project detected"
                                    cp /images/befunge/Dockerfile.template Dockerfile
                                    docker build -t "$PROJECT_NAME" .
                                fi
                            fi

                            if [ -f kubernetes.yaml ]; then
                                echo "Kubernetes configuration detected - Deploying"
                                kubectl apply -f kubernetes.yaml
                            fi
                        """)
                    }
                }
            '''.stripIndent())
        }
    }
}