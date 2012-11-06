class repomgmt($user = 'ubuntu') {
  package { ["python-pip",
             "devscripts",
             "sbuild",
             "git",
             "apache2",
             "rabbitmq-server",
             "ubuntu-dev-tools",
             "reprepro",
             "haveged",
             "vsftpd"]:
    provider => "apt",
    ensure => "installed",
  }

  package { ["django",
             "django-celery",
             "django-tastypie",
             "python-novaclient"]:
    provider => "pip",
    ensure => "installed",
    require => Package['python-pip']
  }

  exec { "/usr/bin/pip install -e git+http://github.com/sorenh/python-django-repomgmt#egg=django-repomgmt":
    require => [Package['git'], Package['python-pip']]
  }

  user { "$user":
    ensure => "present",
    managehome => true,
    groups => "sbuild",
    require => Package['sbuild']
  }

  exec { "/usr/local/bin/django-admin.py startproject buildd":
    creates => "/home/$user/buildd",
    cwd => "/home/$user",
    user => $user
  } ->
  file { "/home/$user/buildd/buildd/settings.py":
    content => template('repomgmt/settings.py.erb'),
    owner => $user
  } ->
  file { "/home/$user/buildd/buildd/urls.py":
    content => template('repomgmt/urls.py.erb'),
    owner => $user
  } ~>
  exec { "/usr/bin/python /home/$user/buildd/manage.py syncdb --noinput":
    user => $user,
    refreshonly => true
  }

  file { "/etc/vsftpd.conf":
    content => template('repomgmt/vsftpd.conf.erb'),
    mode => 0644,
    owner => root,
    group => root,
    require => Package[vsftpd],
    notify => Exec["reload-vsftpd"]
  } 

  file { "/srv/ftp/incoming":
    owner => $user,
    group => ftp,
    mode => "2701",
    require => Package[vsftpd],
  }

  exec { "reload-vsftpd":
    command => "/sbin/restart vsftpd",
    refreshonly => true
  }

  file { "/etc/apache2/conf.d/repomgmt.conf":
    content => template('repomgmt/apache.conf.erb'),
    owner => $user,
    require => Package["apache2"]
  } ~>
  exec { "/etc/init.d/apache2 reload":
    refreshonly => true
  } 
}
